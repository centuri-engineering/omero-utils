"""OMERO widgets for jupyter  notebooks

"""
import base64
import ipywidgets as widgets
from IPython.display import display, Image
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
)
from .roi_utils import get_roi_thumb, html_thumb


class OMEConnect(widgets.VBox):
    """OMERO database connection widget
    """

    def __init__(self, host="localhost", port=4064):
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
        else:
            with self.out:
                ("sorry, connection failed, try again?")
            self.logbox.value = ""
            self.pwdbox.value = ""


class ThumbScatterViz(widgets.VBox):
    def __init__(self, conn, measures, port=4080):

        self.conn = conn
        self.port = port
        self.measures = measures
        self.columns = list(measures.columns)
        selector_layout = widgets.Layout(height="40px", width="100px")
        sbox_layout = widgets.Layout(min_width="120px")
        self.x_selecta = widgets.Dropdown(
            options=self.columns,
            value=self.columns[0],
            description="",
            disabled=False,
            layout=selector_layout,
        )
        self.y_selecta = widgets.Dropdown(
            options=self.columns,
            value=self.columns[1],
            description="",
            disabled=False,
            layout=selector_layout,
        )

        self.c_selecta = widgets.Dropdown(
            options=self.columns,
            value=self.columns[2],
            description="",
            disabled=False,
            layout=selector_layout,
        )

        self.sheet = widgets.Output()
        self.conn = conn
        self.thumbs = {}
        self.goto = widgets.HTML("")
        x_sc = LinearScale()
        y_sc = LinearScale()
        c_sc = ColorScale(scheme="viridis")

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
        self.ax_x = Axis(scale=x_sc, label=self.x_selecta.value, tick_format="0.2f")
        self.ax_y = Axis(scale=y_sc, label=self.y_selecta.value, orientation="vertical")
        self.fig = Figure(marks=[self.scat,], axes=[self.ax_x, self.ax_y],)
        self.scat.on_element_click(self.goto_db)
        self.scat.on_element_click(self.show_data)
        self.scat.on_hover(self.show_thumb)
        self.scat.tooltip = widgets.HTML("")
        self.x_selecta.observe(self.update_scatter)
        self.y_selecta.observe(self.update_scatter)
        self.c_selecta.observe(self.update_scatter)

        super().__init__(
            [
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
                        widgets.VBox([self.fig, Toolbar(figure=self.fig)]),
                    ]
                ),
                widgets.HBox([self.goto, self.sheet]),
            ]
        )

    def update_scatter(self, elem):
        self.scat.x = self.measures[self.x_selecta.value]
        self.ax_x.label = self.x_selecta.value

        self.scat.y = self.measures[self.y_selecta.value]
        self.ax_y.label = self.y_selecta.value
        self.scat.color = self.measures[self.c_selecta.value]

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
    def __init__(self, conn, image, measures, port=4080):

        self.image = image
        super().__init__(conn, measures, port)
        self.base_url = f"""http://{self.conn.host}:{self.port}/webclient/img_detail/{self.image.id}/"""
        if not conn.isConnected():
            conn.connect()
        roi_service = conn.getRoiService()
        self.rois = roi_service.findByImage(
            self.image.getId(), None, conn.SERVICE_OPTS
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
    def __init__(self, conn, measures, port=4080):
        super().__init__(conn, measures, port)
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

            tb.setPixelsId(idx, self.conn.SERVICE_OPTS)
            th = tb.getThumbnailDirect(rint(128), rint(128), self.conn.SERVICE_OPTS)
            th = base64.b64encode(th).decode("utf-8")
            thumb = f'{tag_start}{th}">'
            self.thumbs[idx] = thumb

        return thumb

    def goto_db(self, cbk, target):
        name = target["data"]["name"]
        html_ = self.get_thumb(name)

        url = f"""http://{self.conn.host}:{self.port}/webclient/img_detail/{name}/"""
        self.goto.value = f'<p><hr></p><a href={url} target="_blank">{html_}</a>'
