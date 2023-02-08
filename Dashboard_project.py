# -*- coding: utf-8 -*-

# This is the main file for Dash dashboards based on the group reports for projects.
# by Andrey Chetverikov, 2022

import dash
from dash import callback_context, Dash, DiskcacheManager, Input, Output, dcc, html, ALL, MATCH
import dash_bootstrap_components as dbc

from bids.layout import parse_file_entities
from pathlib import Path
import re, os
import diskcache
import argparse
from uuid import uuid4
from project_dashboard_functions import *
from alive_progress import alive_bar
from datetime import datetime
import json
from helpers import find_free_port

# load stylesheets
app = Dash(use_pages=False,
           external_stylesheets=['https://codepen.io/chriddyp/pen/bWLwgP.css', dbc.themes.BOOTSTRAP]
           )

# thought about using dash pages for better navigation, didn't really manage to get it working
# dash.register_page(__name__)

# read the data from the project folder (Win/Linux)
path_to_data = Path('%s' % 'P:/' if os.name == 'nt' else '/project/')
path_to_data = path_to_data.joinpath('3015999.02/mriqc_data_copy_for_dev')

# base url for individual reports
proj_url = Path('file://///cephsmb.dccn.nl/project_eduvpn/3055010.02/mriqc_data/')

# where to store the cache so that the plots are not generated anew every time
cache = diskcache.Cache(path_to_data.joinpath('../mriqc_dashboard_cache_hpc').as_posix())

# cache is bound to the app instance through uid
launch_uid = uuid4()
background_callback_manager = DiskcacheManager(cache, cache_by=[lambda: launch_uid], expire=3600)


#-------------- read the data -----------------------------------------------------------------------------------------

# paths to look for (project numbers)
path_pattern = re.compile('\\d{7}\\.\\d{2}')

# get all projects within the data folder that match the template and has group reports in them
projects = [path.name for path in path_to_data.iterdir() if
            path_pattern.match(path.name) and path.joinpath('group_bold.tsv').exists()]

# dataframe for the data
data = pd.DataFrame()

total_projects = len(projects)
print('Total projects: %i' % total_projects)

with alive_bar(total_projects) as bar:  # initialize progress bar
    for project in projects:  # go through the projects to collect group BOLD and T1 data

        curData = pd.read_csv(path_to_data.joinpath(project).joinpath('group_bold.tsv'), sep='\t') # read project report
        curData['data_type'] = 'BOLD'
        if path_to_data.joinpath(project).joinpath('group_T1w.tsv').is_file(): # if T1 report is there, read it as well
            curData_t1 = pd.read_csv(path_to_data.joinpath(project).joinpath('group_T1w.tsv'), sep='\t')
            curData_t1['data_type'] = 'T1'
            curData_t1.rename(columns={'snr_total': 'snr'}, inplace=True)
            curData = pd.concat([curData, curData_t1]) # combine with BOLD data

        curData['project'] = project

        # print(curData['bids_name'][1])
        # curData[['subject','session', 'protocol', 'run', 'echo']] = pd.DataFrame(
        #     ('\\'+curData['bids_name'].astype('str')).apply(parse_file_entities).tolist(),
        #     index = curData.index) # split bids name into fields, no longer neeeded

        curData = pd.concat([curData, pd.DataFrame(
            ('\\' + curData['bids_name'].astype('str')).apply(parse_file_entities).tolist(),
            index=curData.index)], axis=1) # parse bids string

        curData.rename(columns={'task': 'protocol'}, inplace=True) # rename 'task' to 'protocol'

        curData['link'] = curData.apply(
            lambda row: proj_url.joinpath(project).joinpath(row.bids_name + '.html').__str__(), axis=1) # add link to individual reports

        try:
            curData['meta.AcquisitionTime'] = pd.to_datetime(curData['meta.AcquisitionTime']) # convert AcquisitionTime to datetime
        except KeyError:
            print('meta.AcquisitionTime is missing in %s' % path_to_data.joinpath(project).joinpath('group_bold.tsv'))

        data = pd.concat([data, curData]) # add data to the full dataframe
        bar()  # update progress bar

data_config = [
    ("snr", 'Signal-to-noise ratio', None),
    ("fd_mean", 'Mean framewise-displacement', "mm"),
    ("efc", "Entropy-focus criterion", None),
    # ("fber", 'Foreground-Background energy ratio', None),
    # ("fwhm_avg","Image intensity full-width half-maximum (FWHM)")
]

measure_vars = [x[0] for x in data_config]
data.columns = data.columns.str.replace("^meta.", "meta_", regex=True)

print(data.columns)

# data = pd.melt(data, id_vars = ['subject','session', 'task', 'run', 'echo','bids_name'],
#                value_vars = measure_vars)

# variables to filter on in the left panel; displayed name is followed by variable name
filter_types = {'scanner': 'meta_StationName', 'project': 'project', 'protocol': 'protocol'}

# variables to be used as x-axis in the plots (selectable in the dashboard); displayed name is followed by variable name
x_axis_types = {'time': 'meta_AcquisitionTime', 'project': 'project', 'subject': 'subject', 'protocol': 'protocol',
                'scanner': 'meta_StationName'}

# ------create the dashboard ----------------------------------------------------------------------------------------

# the control panel in the dashboard
controls = dbc.Card(
    [html.H3('Filter the QC data'), # header
     html.Div(id='filter_container', children= # for each filter type, create a dropdown menu
     # [dcc.Dropdown(id = 'temp', options=[])]+
     [html.Div([dbc.Label("Filter data by %s" % filter_type),
                dcc.Dropdown(
                    id={'name': filter_type, 'type': 'plot-filter', 'variable': filter_var},
                    options=[
                                {"label": col, "value": col} for col in data[filter_var].unique() if
                                col != '' and col == col  # note that this col==col bit is to get rid of nan values
                            ] + [{"label": 'all %ss' % filter_type, "value": ''}], # include 'all' option
                    value='',
                    clearable=False
                )]) for filter_type, filter_var in filter_types.items()
      ]
              ),
     html.H3('Configure the plots'), # a dropdown menu for the x-axis selector
     html.Div([
         dbc.Label('Choose x-axis'),
         dcc.Dropdown(
             id='plots_x_axis',
             options=[
                 {"label": label, "value": var} for label, var in x_axis_types.items()
             ],
             value=list(x_axis_types.values())[0],
             clearable=False
         )]
     )],
    body=True
)

# overall container for the page
app.layout = dbc.Container(
    children=[
        dbc.Row([
            dbc.Col(controls, xs=12, sm=12, md=2), # control panel
            dbc.Col(dbc.Spinner(size='md'), id='spinner'), # a spinner shown during loading
            dbc.Col(dbc.Row([                       # the graphs
                dbc.Col([html.Div(id='graph_containter_BOLD')]),
                dbc.Col(html.Div(id='graph_containter_T1'))
            ]))
        ]),
        dbc.Row([dbc.Col(html.Div())], id='placeholder_for_outputs'), # a placeholder for debugging outputs
    ],
    fluid=True,
    className='p-3'
)

#------------------- callback to create the graphs based on selected control settings-----------------------------------
# Inputs: all control panel filters
# Outputs: graph containers and control filters (to filter out unavailable options based on other options)

@app.callback(
    Output(component_id="graph_containter_BOLD", component_property="children"),
    Output(component_id="graph_containter_T1", component_property="children"),
    Output({'type': 'plot-filter', 'name': 'scanner', 'variable': filter_types['scanner']}, "options"),
    Output({'type': 'plot-filter', 'name': 'project', 'variable': filter_types['project']}, "options"),
    Output({'type': 'plot-filter', 'name': 'protocol', 'variable': filter_types['protocol']}, "options"),
    # Output("filter_container", "children"),
    Input({'type': 'plot-filter',
           'name': ALL,
           'variable': ALL}, 'value'),
    Input('plots_x_axis', 'value'),
    background=True, # runs in the background, using cache
    manager=background_callback_manager,
    running=[
        (Output('spinner', 'style'), {}, {'display': 'none'}), # show spinner while running, hide when completed
        (Output('graph_containter_BOLD', 'style'), {'display': 'none'}, {}), # hide graphs while running, show when completed
        (Output('graph_containter_T1', 'style'), {'display': 'none'}, {})
        # (Output('placeholder_for_outputs', 'display'), 'None', 'visible')
    ]
)
def make_graph(filters, x_axis_variable): # the inputs are the filters and the x-axis variable
    # for debugging
    print(filters)
    print(dash.callback_context.inputs)
    # print(dash.callback_context.inputs_list)
    print('Rebuilding graph with %s on x axis' % x_axis_variable)

    # make sure that x-axis variable is set correctly
    assert x_axis_variable is None or x_axis_variable in ['', 'none'] + list(x_axis_types.values())
    if x_axis_variable is None or x_axis_variable == '': # set to default when empty
        x_axis_variable = list(x_axis_types.values())[0]

    filtered_data = data
    current_filter_values = {}

    # recursively filter the data based on the filters
    for curFilter in callback_context.inputs_list[0]:
        filter_type = curFilter['id']['variable']
        filter_value = curFilter['value']
        current_filter_values[filter_type] = filter_value
        if filter_value is not None and filter_value in filtered_data[filter_type].unique():
            filtered_data = filtered_data.loc[filtered_data[filter_type] == filter_value]

    # for each of the filters update other filters to only show the possible filter combinations
    possible_values_for_filters = {}
    for filter_type, filter_var in filter_types.items():
        # possible_values_for_filters[filter_type] = [['all %ss' % filter_type, '']] + [[x, x] for x in filtered_data[filter_var].unique()]
        possible_values_for_filters[filter_type] = [
                                                       {"label": col, "value": col} for col in
                                                       filtered_data[filter_var].unique() if col != '' and col == col
                                                       # note that this col==col bit is to get rid of nan values
                                                   ] + [{"label": 'all %ss' % filter_type, "value": ''}]
    print(possible_values_for_filters)

    # create plots for each variable
    graphs = {'BOLD': [], 'T1': []}
    for variable in measure_vars:
        for data_type in ['T1', 'BOLD']:
            # print(filtered_data)
            data_to_use = filtered_data.loc[filtered_data['data_type'] == data_type]
            title = [i[1] for i in data_config if i[0] == variable][0] + ' ' + data_type
            print('%s %s %i' % (variable, data_type, data_to_use.shape[0]))
            if data_to_use.shape[0] > 0 and not data_to_use[variable].isnull().all():
                if (x_axis_variable == 'meta_AcquisitionTime'):
                    graph = makeTimeGraph(data_to_use, variable, x_axis_variable, title, x_axis_types) # time graph
                else:
                    graph = makeBarGraph(data_to_use, variable, x_axis_variable, title, x_axis_types) # bar (violin) graph
                graphs[data_type].append(graph)

    # all_graphs = [dbc.Col(graphs['BOLD']), dbc.Col(graphs['T1'])]

    return (
        graphs['BOLD'], graphs['T1'],
        possible_values_for_filters['scanner'], possible_values_for_filters['project'],
        possible_values_for_filters['protocol'])


# ------ callbacks for point clicks  ----------------------------------------------------------------------------------------
# client-side callbacks for point clicks - does not help
# app.clientside_callback(
#     """
#     function(clickData) {
# //         if len(callback_context.triggered)>0 and len(clickData_filtered)>0 and clickData_filtered[0] is not None and \
# //             'points' in clickData_filtered[0].keys() and len(clickData_filtered[0]['points'])>0:
#     clickData_filtered = clickData.filter(element => {
#       return element !== undefined;
#     });
#     if (clickData_filtered.length > 0){
#         url = clickData_filtered[0]['points'][0]['id'];
#         window.open(url);
#     }
#
#     return ['', '', '', '']; // clear clickData
#     }
#     """,
#     Output('placeholder_for_outputs', 'children'),
#     Output(dict(type='graph', id = ALL), 'clickData'),
#     Input(dict(type='graph', id = ALL), 'clickData')
# )

# server-side callbacks for point clicks
# currently works to show the urls below the plots but in the wrong places

# Inputs: receives data from all graphs once a point on the graph is clicked on
# Outputs: modifies graphs (to reset click data), their footers (to show urls to individual reports), and the placeholder (for debugging)
@app.callback(
    Output('placeholder_for_outputs', 'children'),
    Output(dict(type='graph', id=ALL), 'clickData'),
    Output(dict(type='graph_footer', id=ALL), 'children'),
    Input(dict(type='graph', id=ALL), 'clickData'),
    Input(dict(type='graph', id=ALL), 'selectData')
)
def callback_function(clickData, selectData): # selectData is not currently used

    # for debugging
    print('clicked clocked at %s' % datetime.now())
    print('clickData:')
    print(json.dumps(clickData, indent=2, sort_keys=True))
    print('selectData:')
    print(json.dumps(selectData, indent=2, sort_keys=True))
    print('\ncallback_context.triggered:')
    print(json.dumps(callback_context.triggered, indent=2, sort_keys=True))

    # select only non-empty clickData objects (clickData is an array with the number of objects corresponding to the number of plots)
    clickData_filtered = [x for x in clickData if x]
    # clickData_filtered_i = [i for i, x in enumerate(clickData) if x]

    output_urls = [None] * len(clickData) # initialize empty object for urls

    # many filters to ensure that only the right objects are chosen
    if len(callback_context.triggered) > 0 and len(clickData_filtered) > 0 and clickData_filtered[0] is not None and \
            'points' in clickData_filtered[0].keys() and len(clickData_filtered[0]['points']) > 0:
        # 'value' in callback_context.triggered[0].keys() and \
        # callback_context.triggered[0]['value'] is not None:
        # url = callback_context.triggered[0]['value']['points'][0]['id']

        # get the url for the clicked point
        url = clickData_filtered[0]['points'][0]['id']

        # output_urls[clickData_filtered_i[0]] = url
        output_urls = [url] * len(clickData)
        print('opening new tab for %s' % url) # for debugging
        # webbrowser.open_new_tab(url) # does not work well when multiple people are using the dashboard

    # return ['%s\n%s' % (json.dumps(callback_context.triggered, indent=2), json.dumps(clickData, indent=2)), [None]*len(clickData)]
    print(output_urls)

    # return empty string for the placeholder, resets clickData for all plots, sets the output urls in the footers
    return ['', [None] * len(clickData), output_urls]

#------------------------------------app initialization-----------------------------------------------------------------


ap = argparse.ArgumentParser()
ap.add_argument("-p", "--port", default='0', required=False, help="port to use, 0 means any available port")

args = vars(ap.parse_args())
port = args['port']

if port == '0':
    port = 36631  # find_free_port() # for debugging, set to fixed port

if __name__ == '__main__':
    app.run_server(debug=False, host='0.0.0.0', port=port)
