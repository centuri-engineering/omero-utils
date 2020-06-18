"""OMERO widgets for jupyter  notebooks

"""
import base64
from time import sleep
import ipywidgets as widgets
from IPython.display import display, Image
import omero
from omero.gateway import BlitzGateway
from omero.rtypes import rint
import pandas as pd
from bqplot import (
    Figure,
    Scatter,
    LinearScale,
    Axis,
    Toolbar,
    ColorScale,
    ColorAxis,
    DateScale,
    DateColorScale,
)

from .roi_utils import get_roi_thumb, html_thumb


class OMEConnect(widgets.VBox):
    """OMERO database connection widget
    """

    def __init__(self, host="localhost", port=4064):
        """Connects to an omero database.

        Parameters
        ----------
        host: str, the omero server host (default localhost)
        port: int, the connection port (default 4064)

        """
        self.host = host
        self.port = port
        self.logbox = widgets.Text(description="OME loggin")
        self.pwdbox = widgets.Password(description="OME password")
        self.gobtn = widgets.Button(description="Let me in")
        self.gobtn.on_click(self.on_go_clicked)
        self.out = widgets.Output()
        super().__init__((self.logbox, self.pwdbox, self.gobtn, self.out))
        self.conn = None

    def on_go_clicked(self, b):
        self.out.clear_output()

        if self.conn is not None:
            self.conn.close()

        self.conn = BlitzGateway(
            self.logbox.value, self.pwdbox.value, host=self.host, port=self.port
        )
        self.conn.connect()
        if self.conn.isConnected():
            with self.out:
                print("Logging successful!\n")
                display(Image("https://media.giphy.com/media/Azwmdv1NTSe9W/giphy.gif"))
                sleep(3)
                self.out.clear_output()
        else:
            with self.out:
                ("sorry, connection failed, try again?")
            self.logbox.value = ""
            self.pwdbox.value = ""


class ThumbScatterViz(widgets.VBox):
    def __init__(
        self,
        measures,
        x=None,
        y=None,
        c=None,
        mouseover=False,
        host="localhost",
        port=4090,
    ):
        """Interactive scatter plot visualisation - this is a base class,
        use either `ROIScatterViz` for one image with multiple ROIs
        or `ImageScatterViz` for a scatterplot with multiple images
        """
        self.port = port
        self.measures = measures
        self.columns = list(measures.columns)
        x_col = x if x else self.columns[0]
        y_col = y if y else self.columns[1]
        c_col = c if c else self.columns[2]

        selector_layout = widgets.Layout(height="40px", width="100px")
        self.x_selecta = widgets.Dropdown(
            options=self.columns,
            value=x_col,
            description="",
            disabled=False,
            layout=selector_layout,
        )
        self.y_selecta = widgets.Dropdown(
            options=self.columns,
            value=y_col,
            description="",
            disabled=False,
            layout=selector_layout,
        )

        self.c_selecta = widgets.Dropdown(
            options=self.columns,
            value=c_col,
            description="",
            disabled=False,
            layout=selector_layout,
        )

        self.sheet = widgets.Output()
        self.thumbs = {}
        self.goto = widgets.HTML("")
        if is_datetime(self.measures, x_col):
            x_sc = DateScale()
        else:
            x_sc = LinearScale()

        if is_datetime(self.measures, y_col):
            y_sc = DateScale()
        else:
            y_sc = LinearScale()

        if is_datetime(self.measures, c_col):
            c_sc = DateColorScale(scheme="viridis")
        else:
            c_sc = ColorScale()

        self.scat = Scatter(
            x=self.measures[self.x_selecta.value],
            y=self.measures[self.y_selecta.value],
            color=self.measures[self.c_selecta.value],
            scales={"x": x_sc, "y": y_sc, "color": c_sc,},
            names=self.measures.index,
            display_names=False,
            fill=True,
            default_opacities=[0.8,],
        )
        self.ax_x = Axis(scale=x_sc, label=self.x_selecta.value)
        self.ax_y = Axis(scale=y_sc, label=self.y_selecta.value, orientation="vertical")
        self.ax_c = ColorAxis(
            scale=c_sc,
            label=self.c_selecta.value,
            orientation="vertical",
            offset={"scale": y_sc, "value": 100},
        )
        self.fig = Figure(marks=[self.scat,], axes=[self.ax_x, self.ax_y, self.ax_c],)
        self.scat.on_element_click(self.goto_db)
        self.scat.on_element_click(self.show_data)
        if mouseover:
            self.scat.on_hover(self.show_thumb)
            self.scat.tooltip = widgets.HTML("")
        self.x_selecta.observe(self.update_scatter)
        self.y_selecta.observe(self.update_scatter)
        self.c_selecta.observe(self.update_scatter)
        self.connector = OMEConnect(host=host, port=4064)
        self.connector.gobtn.on_click(self.setup_graph)
        super().__init__([self.connector])

    def setup_graph(self, btn):

        if self.connector.conn is None:
            return

        self.conn = self.connector.conn
        wait = 0
        while not self.connector.conn.isConnected():
            sleep(1)
            wait += 1
            if wait > 30:
                self.children = [widgets.HTML("<a><h4>Connection time out</h4></a>")]
                return

        sbox_layout = widgets.Layout(min_width="120px")
        fig_layout = widgets.Layout(max_width="800px")
        self.children = [
            widgets.HBox(
                [
                    widgets.VBox(
                        [
                            widgets.HTML("<a><h4>x axis</h4></a>"),
                            self.x_selecta,
                            widgets.HTML("<a><h4>y axis</h4></a>"),
                            self.y_selecta,
                            widgets.HTML("<a><h4>color</h4></a>"),
                            self.c_selecta,
                        ],
                        layout=sbox_layout,
                    ),
                    widgets.VBox(
                        [self.fig, Toolbar(figure=self.fig)], layout=fig_layout
                    ),
                    widgets.VBox([self.goto, self.sheet], layout=sbox_layout),
                ]
            ),
        ]

    def update_scatter(self, elem):
        col = self.x_selecta.value
        if is_datetime(self.measures, col):
            x_sc = DateScale()
        else:
            x_sc = LinearScale()
        self.ax_x.scale = x_sc
        self.scat.x = self.measures[col]
        self.ax_x.label = col

        col = self.y_selecta.value
        if is_datetime(self.measures, col):
            y_sc = DateScale()
        else:
            y_sc = LinearScale()
        self.ax_y.scale = y_sc
        self.scat.y = self.measures[col]
        self.ax_y.label = col

        col = self.c_selecta.value
        if is_datetime(self.measures, col):
            c_sc = DateColorScale()
        else:
            c_sc = ColorScale()
        self.ax_c.scale = c_sc
        self.scat.color = self.measures[col]
        self.ax_c.label = col
        self.scat.scales = {
            "x": x_sc,
            "y": y_sc,
            "color": c_sc,
        }

    def get_thumb(self, idx):
        raise NotImplementedError

    def show_thumb(self, cbk, target):
        name = target["data"]["name"]
        self.scat.tooltip = widgets.HTML("")
        self.scat.tooltip = widgets.HTML(self.get_thumb(name))
        self.scat.tooltip.style = {"opacity": 1.0}

    def goto_db(self, cbk, target):
        raise NotImplementedError

    def show_data(self, cbk, target):
        self.sheet.clear_output()
        name = target["data"]["name"]
        active_cols = [
            self.x_selecta.value,
            self.y_selecta.value,
            self.c_selecta.value,
        ]
        with self.sheet:
            display(pd.DataFrame(self.measures.loc[name, active_cols]))


class ROIScatterViz(ThumbScatterViz):
    """Interactive Scatter plot widget for ROI related measurement data.

    Each line in the input `measure` DataFrame corresponds to a ROI
    """

    def __init__(
        self,
        image_id,
        measures,
        x=None,
        y=None,
        c=None,
        mouseover=False,
        port=4090,
        host="localhost",
    ):
        """
        Parameters
        ----------
        image : an omero `Image` instance
        measures : a pandas `DataFrame`
        x, y, c : column names from measures
           those will be used as the x, y and color values for the initial plot
        port : int, default 4090, the port to connect to the DB
        mouseover : bool, default False
            if True, will display a thumbnail as mouse over tooltip - might be lagging

        """
        self.image_id = image_id
        self.image = None
        self.base_url = None
        super().__init__(
            measures, x=x, y=y, c=c, port=port, mouseover=mouseover, host=host
        )

    def setup_graph(self, btn):

        super().setup_graph(btn)
        self.image = self.conn.getObject("Image", self.image_id)
        self.base_url = f"""https://{self.conn.host}:{self.port}/webclient/img_detail/{self.image.id}/"""
        if not self.conn.isConnected():
            self.conn.connect()
        roi_service = self.conn.getRoiService()
        self.rois = roi_service.findByImage(
            self.image.getId(), None, self.conn.SERVICE_OPTS
        ).rois

    def get_thumb(self, idx):

        th = self.thumbs.get(idx)
        if th is None:
            roi = self.rois[idx]
            th = html_thumb(get_roi_thumb(self.conn, self.image, roi, draw_roi=True))
            self.thumbs[idx] = th
        return th

    def goto_db(self, cbk, target):
        name = target["data"]["name"]
        html_ = self.get_thumb(name)
        try:
            pixel_size = self.image.getPrimaryPixels().getPhysicalSizeX().getValue()
        except AttributeError:
            pixel_size = 1
        current = self.measures.loc[name]
        xc, yc = int(current.X / pixel_size), int(current.Y / pixel_size)
        coords = f"?x={xc}&y={yc}&zm=400"
        colors = "&c=1|0:255$FF0000,2|0:255$00FF00,3|0:255$0000FF,-4|0:255$FF0000&m=c"
        url = self.base_url + coords + colors
        self.goto.value = f'<p><hr></p><a href={url} target="_blank">{html_}</a>'


class ImageScatterViz(ThumbScatterViz):
    def __init__(
        self,
        measures,
        x=None,
        y=None,
        c=None,
        port=4090,
        mouseover=False,
        host="localhost",
    ):
        """Scatterplot with dynamic link to images in an omero database

        Parameters
        ----------
        conn : a `BlitzGateway` connection to an omero database
        measures : a `pandas.DataFrame` indexed by the images id in the database
        x: str, a column from the measures for the x axis
        y: str, a column from the measures for the y axis
        c: str, a column from the measures for the color scale

        mouseover: bool, default False
            if True, displays a thumbnail of the image when the mouse is over a point
        """
        super().__init__(
            measures, x=x, y=y, c=c, port=port, mouseover=mouseover, host=host
        )
        self.thumbs = {}

    def get_thumb(self, idx):

        thumb = self.thumbs.get(idx)
        tag_start = (
            '<img style="width: 200px; max-height: 200px" src="data:image/jpg;base64,'
        )
        if thumb is None:
            self.conn.connect()
            self.conn.SERVICE_OPTS.setOmeroGroup("-1")
            tb = self.conn.createThumbnailStore()
            try:
                tb.setPixelsId(idx, self.conn.SERVICE_OPTS)
                th = tb.getThumbnailDirect(rint(128), rint(128), self.conn.SERVICE_OPTS)
                th = base64.b64encode(th).decode("utf-8")
                thumb = f'{tag_start}{th}">'
            except omero.ResourceError:
                thumb = "<p>Image not reachable</p>"

            self.thumbs[idx] = thumb

        return thumb

    def goto_db(self, cbk, target):
        name = target["data"]["name"]
        html_ = self.get_thumb(name)

        url = f"""https://{self.conn.host}:{self.port}/webclient/img_detail/{name}/"""
        self.goto.value = f'<p><hr></p><a href={url} target="_blank">{html_}</a>'


def is_datetime(data, col):

    return hasattr(data[col], "dt")
