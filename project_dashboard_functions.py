# -*- coding: utf-8 -*-

# functions to create dashboard plots
# by Andrey Chetverikov, 2022

from dash import dcc, html
import plotly.graph_objs as go
from sklego.linear_model import LowessRegression
import numpy as np
import pandas as pd


# a bar (violin) plot
def makeBarGraph(filtered_data, variable, x_axis_variable, title, x_axis_types):
    """ Creates violin plots for the filtered dataset.

    Parameters:
        filtered_data : a pandas.DataFrame with the data
        variable : the variable plotted on y-axis
        x_axis_variable : the variable on x-axis
        title : plot title
        x_axis_types : extra variables shown in the tooltips on hover

    Returns:
        graph : a Dash Div object with a plot (dcc.Graph) and a footer (Div) inside
    """

    # show outliers points only if the total number of points above 100
    if filtered_data.shape[0] > 100:
        showPoints = 'outliers'
    else:
        showPoints = 'all'

    # all except the x-axis variable are added in the hover
    extra_vars = {k: v for k, v in x_axis_types.items() if v != x_axis_variable}

    # convert relevant data to numpy array to be parsed by Dash in the hover template
    po_custom_data = filtered_data[[v for k, v in extra_vars.items()] + ['link']].to_numpy()

    # set up a hover template
    hover_template = "<b>Date</b>: %{x}<br>"
    hover_template += "<b>%s</b>: %%{y}<br>" % title
    hover_template += '<br>'.join([f'<b>{k}</b>: %{{customdata[{i}]}}' for i, k in enumerate(extra_vars)])
    # hover_template += '<br>{link}</br>'
    hover_template += '<extra></extra>'

    # print(hover_template)

    # create the graph object
    dcc_graph_obj = dcc.Graph(
        id={'type': 'graph',  # html id with two components for Dash manipulations
            'id': variable},
        figure={
            'data': [  # data for the plot
                go.Violin(
                    y=filtered_data[(filtered_data[x_axis_variable] == i)][variable],
                    points=showPoints,
                    box={"visible": True},
                    hovertemplate=hover_template,
                    customdata=po_custom_data,  # custom data is parsed through the hover template
                    ids=filtered_data[(filtered_data[x_axis_variable] == i)]['link'],
                    # point ID is the link to the repiort
                    hoveron='points',
                    opacity=0.7,
                    marker={
                        'size': 10,
                        'line': {'width': 0.5, 'color': 'white'}
                    },
                    name=i
                ) for i in filtered_data[x_axis_variable].unique()
            ],
            'layout': go.Layout(
                title=title,
                yaxis={'title': title,
                       'zeroline': False},
                xaxis={'type': 'category', 'title':
                    [label for label, var in x_axis_types.items() if var == x_axis_variable][0].capitalize(),
                       'automargin': True},
                # margin={'l': 40, 'b': 40, 't': 30, 'r': 10},
                legend={'x': 0, 'y': 1},
                hovermode='closest',
                showlegend=False,
                clickmode='event+select'
            )}
    )

    # combine with the footer in a Div and return
    graph = html.Div(className='col-auto',
                     children=[dcc_graph_obj, html.Div(id={'type': 'graph_footer',
                                                           'id': variable})])
    return graph


def makeTimeGraph(filtered_data, variable, x_axis_variable, title, extra_vars):
    """ Creates points-and-average plots to show time dependency for the filtered dataset.

    Parameters:
        filtered_data : a pandas.DataFrame with the data
        variable : the variable plotted on y-axis
        x_axis_variable : the variable on x-axis (normally, time)
        title : plot title
        extra_vars : extra variables shown in the tooltips on hover

    Returns:
        graph : a Dash Div object with a plot (dcc.Graph) and a footer (Div) inside
    """

    # sort the data by x_axis_variable (time)
    filtered_data = filtered_data.sort_values(by=x_axis_variable)

    # select only the x and y variables for smoothing
    x_for_smooth = filtered_data[x_axis_variable]

    # potentially rebase, not used
    # (x_for_smooth - min(x_for_smooth)).dt.total_seconds()
    # x_for_smooth = (x_for_smooth-min(x_for_smooth)).dt.total_seconds()
    y_for_smooth = filtered_data[variable]

    npoints = filtered_data.shape[0]

    # convert to numpy arrays
    x_for_fit = np.array(x_for_smooth)
    y_for_fit = np.array(y_for_smooth)
    y_for_fit = y_for_fit[~np.isnan(x_for_fit)]
    x_for_fit = x_for_fit[~np.isnan(x_for_fit)].astype('float')

    # scale for smoothing
    min_ts = min(x_for_fit)
    max_ts = max(x_for_fit)
    x_for_fit = (x_for_fit - min_ts) / (max_ts - min_ts)
    fit_range = np.ptp(x_for_fit)

    # smooth with Lowess using a narrow kernel
    mod = LowessRegression(sigma=fit_range / 1000).fit(x_for_fit.reshape(-1, 1), y_for_fit.flatten())

    # get the smoothed average
    # define a grid for predictions
    pred_x = np.linspace(np.double(np.min(x_for_fit)), np.double(np.max(x_for_fit)), 100)
    pred_x_ts = pd.to_datetime(min_ts + pred_x * (max_ts - min_ts), unit='ns')

    # pred_x = pd.date_range(min(x_for_fit), max(x_for_fit), periods=500)
    # pred_x = np.array(pred_x.astype('float')).reshape(-1,1)
    preds = mod.predict(pred_x.reshape(-1, 1))  # predicted values

    # hover template

    # all except the x-axis variable are added in the hover
    extra_vars = {k: v for k, v in extra_vars.items() if v != x_axis_variable}

    # convert relevant data to numpy array to be parsed by Dash in the hover template
    po_custom_data = filtered_data[[v for k, v in extra_vars.items()] + ['link']].to_numpy()

    # set the template
    hover_template = "<b>Date</b>: %{x}<br>"
    hover_template += "<b>%s</b>: %%{y}<br>" % title

    hover_template += '<br>'.join([f'<b>{k}</b>: %{{customdata[{i}]}}' for i, k in enumerate(extra_vars)])

    hover_template += '<extra></extra>'
    # hover_template += '<br><br><a href = "file://{custom_data[%i]}">detailed report</a>' % len(extra_vars) # would be easy, right? but no, can't do that as the hover disappers and you can't clicik on the link
    # print(hover_template)

    # create the graph object as a combination of points and line
    dcc_graph_obj = dcc.Graph(
        id={'type': 'graph',  # html id with two components for Dash manipulations
            'id': variable + '_temporal'},
        figure={
            'data': [
                go.Scatter(
                    x=filtered_data[x_axis_variable],
                    y=filtered_data[variable],
                    mode='markers',
                    ids=filtered_data['link'],
                    opacity=0.7,
                    customdata=po_custom_data,
                    hovertemplate=hover_template,
                    # hovertext=df.loc[df['scanner'] == i]['paul_notes'],
                    marker={
                        'size': np.min([10, np.max([5, 10 - np.log(npoints)])]),
                        'line': {'width': 0.5, 'color': 'white'}
                    },
                    line={'shape': 'spline'},
                    name='data'
                ),
                go.Scatter(name='running average', x=pred_x_ts, y=preds, mode='lines')
            ],
            'layout': go.Layout(
                title=title,
                xaxis={'title': 'Date', 'zeroline': False},
                yaxis={'title': title, 'zeroline': False},
                margin={'l': 40, 'b': 40, 't': 30, 'r': 10},
                # shapes=shapes_lines,
                # annotations=annotations,
                legend={'x': 0, 'y': 1},
                hovermode='closest',
                clickmode='event+select'
            )}
    )

    # add a footer and return
    graph_temporal = html.Div(className='col-auto',
                              children=[dcc_graph_obj, html.Div(id={'type': 'graph_footer',
                                                                    'id': variable})])

    return graph_temporal
