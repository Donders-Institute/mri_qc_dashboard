# -*- coding: utf-8 -*-
# This is the main script for the Dash dashboard based on phantom measurements

import webbrowser
import dash, json
from dash import dcc, html, MATCH, ALL
import pandas as pd
import plotly.graph_objs as go
from dash.dependencies import Input, Output
import argparse
from pathlib import Path
from helpers import *
import os

# setting the path
default_path = Path('%s/3055010.02/BIDS_data' % ('P:' if os.name == 'nt' else '/project'))

ap = argparse.ArgumentParser()
ap.add_argument("-p", "--port", default='0', required=False, help="port")

scanners = ['Prisma','Prismafit','Skyra'] # a list of scanner names
qc_types = {'fMRI':'fMRI','short':'Individual coil check'} # a list of QC types
# the dictionary of sections defines which plots are created for each QC type
sections = {'fMRI':
                [{'name': 'Temporal Signal to Noise Ratio', 'id': 'tSNR'},
                {'name': 'Ghost to Signal Ratio', 'id': 'GSR', 'ytitle': 'Ghost to Signal Ratio (%)'},
                {'name': 'Reference Amplitude', 'id': 'ref_amp'},
                {'name': 'Maximum Displacement', 'id': 'max_displacement', 'ytitle': 'Maximum Displacement (voxels)'}],
            'short':
                [{'name': 'Maximum deviation from center of mass median from 5 latest measurements', 'id': 'max_dev',
                'yaxis': 'maximum center of mass deviation (voxels)'},
                {'name': 'Maximum deviation from single coil signal proportion from 5 latest measurements',
                 'id': 'max_prop_dev', 'yaxis': 'maximum signal proportion deviation (%)'}
                ]

}

args = vars(ap.parse_args())
port = args['port']

df_list = []

def read_file(path_to_data):
    """ Read the path (absolute or relative to the default path) or throw an error"""
    if Path(path_to_data).exists():
        file_found = True
    elif default_path.joinpath(path_to_data).exists():
        path_to_data = default_path.joinpath(path_to_data)
    else:
        raise FileNotFoundError('File ' + path_to_data + ' or '+str(default_path.joinpath(path_to_data))+' does not exist')
    return pd.read_csv(path_to_data)

# Data Preparation - Reading CSV files and adding a scanner column
for file_type in scanners:
    for qc_type in qc_types:
        path_to_data = 'sub-%s/full_data_%s.csv' % (file_type, qc_type)
        df = read_file(path_to_data)
        df['scanner'] = file_type
        df['qc_type'] = qc_type
        df_list.append(df)

df_events = read_file('events.csv')

# Concatenate data
full_df = pd.concat(df_list)
full_df['link'] = full_df.apply(lambda row: default_path.joinpath(
    'sub-' + row.scanner + '/ses-' + str(row.date) + '_phantom'+('_fMRI' if row.qc_type == 'fMRI' else '')+'.html').__str__(), axis=1)
full_df["paul_notes"] = ""

# Convert Date to datetime format
full_df.date = pd.to_datetime(full_df.date, format='%Y%m%d')

# Style components
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

# Convert dates in events dataframe to actual datetimes
df_events['date_start'] = pd.to_datetime(df_events['date_start'], format='%d/%m/%Y')
df_events['date_end'] = pd.to_datetime(df_events['date_end'], format='%d/%m/%Y')

# choose colors based on the scanner id
def color_switch(argument):
    switcher = {
        "Skyra": "Blue",
        "Prismafit": "Green",
        "Prisma": "Orange",
        "Multiple": "Black",
    }
    return (switcher.get(argument))

# these "shapes_lines" and annotations are used for the QC notes in the temporal plot later
shapes_lines = list()
annotations = list()
for index, row in df_events.iterrows():
    color = color_switch(row['scanner'])
    shapes_lines.append({'type': 'rect',
                         'xref': 'x',
                         'yref': 'paper',
                         'x0': row['date_start'],
                         'y0': 0.5,
                         'x1': row['date_end'],
                         'y1': 0.6,
                         'line': {'color': color,
                                  'width': 2
                                  },
                         'fillcolor': color,
                         'opacity': 0.3
                         })

    annotations.append({'text': row['description'],
                        'xref': 'x',
                        'yref': 'paper',
                        'x': row['date_start'] + (row['date_end'] - row['date_start']) / 2,
                        'y': .45,
                        'showarrow': False

                        })

for index, row in df_events.iterrows():
    if row['scanner'] == 'Multiple':
        full_df.loc[(full_df['date'] >= row['date_start']) & (full_df['date'] <= row['date_end']), 'paul_notes'] = row[
            'long_description']
    full_df.loc[(full_df['date'] >= row['date_start']) & (full_df['date'] <= row['date_end']) & (
                full_df['scanner'] == row['scanner']), 'paul_notes'] = row['long_description']


section_list = [html.Div(id = 'placeholder_for_outputs')]

section_index = -1
# creates plots for all QC types in a loop
# for each QC type, there are multiple plots as defined in sections
for qc_type, qc_type_header in qc_types.items():
    section_list.append(html.H1(qc_type_header))
    print(qc_type)
    df = full_df[full_df['qc_type'] == qc_type]

    for section in sections[qc_type]:
        section_index += 1
        title = html.H4(children=section['name'])
        graph_summary = dcc.Graph(
            id = {'type': 'point_graph',
                  'name': section['id'] + '_box'},
            figure = {
                'data': [
                    go.Violin(
                        y=df[df['scanner'] == i][section['id']],
                        points='all',
                        box={"visible": True},
                        customdata=df.loc[df['scanner'] == i]['link'],
                        opacity=0.7,
                        marker={
                            'size': 10,
                            'line': {'width': 0.5, 'color': 'white'}
                        },
                        name=i
                    ) for i in df.scanner.unique()
                ],
                'layout': go.Layout(
                    title="Distribution",
                    yaxis={'title': section['yaxis'] if 'yaxis' in section.keys() else section['name'],
                           'zeroline': False},
                    margin={'l': 40, 'b': 40, 't': 30, 'r': 10},
                    legend={'x': 0, 'y': 1},
                    hovermode='closest',
                    clickmode='event'
                )}
        )

        graph_temporal = dcc.Graph(
            id = {'type': 'point_graph',
                'name': section['id'] + '_temporal'},
            figure={
                'data': [
                    go.Scatter(
                        x=df[df['scanner'] == i]['date'],
                        y=df[df['scanner'] == i][section['id']],
                        mode='lines+markers',
                        customdata=df.loc[df['scanner'] == i]['link'],
                        opacity=0.7,
                        hovertext=df.loc[df['scanner'] == i]['paul_notes'],
                        marker={
                            'size': 10,
                            'line': {'width': 0.5, 'color': 'white'}
                        },
                        name=i
                    ) for i in df.scanner.unique()

                ],
                'layout': go.Layout(
                    title=section['name'],
                    xaxis={'title': 'Date', 'zeroline': False},
                    yaxis={'title': section['yaxis'] if 'yaxis' in section.keys() else section['name'], 'zeroline': False},
                    margin={'l': 40, 'b': 40, 't': 30, 'r': 10},
                    shapes=shapes_lines,
                    annotations=annotations,
                    legend={'x': 0, 'y': 1},
                    hovermode='closest',
                    clickmode='event'
                )}
        )
        section_list.append(html.Div(
            [title, html.Div([
                html.Div(graph_summary, className='six columns', style={'width': '30%'}),
                html.Div(graph_temporal, className='six columns', style={'width': '65%'})
            ], className='row')]
        ))

#print(section_list)

# App Layout
app.layout = html.Div(children=section_list)

@app.callback(
    Output('placeholder_for_outputs', 'children'),
    [Input(dict(type='point_graph', name = ALL), 'clickData')]
)
def callback_function(clickData):
    #print('clicked clocked')
    if len(dash.callback_context.triggered)>0 and 'value' in dash.callback_context.triggered[0].keys() and dash.callback_context.triggered[0]['value'] is not None:
        webbrowser.open_new_tab(dash.callback_context.triggered[0]['value']['points'][0]['customdata'])
    return json.dumps(dash.callback_context.triggered, indent=2)


if port == '0':
    port = find_free_port()

app.run_server(debug=False,
               host='0.0.0.0', port=port)
