"""OMERO connection widgets from jupyter  notebooks (and maybe others)

"""

import ipywidgets as widgets
import warnings
from IPython.display import display, Image
from skimage.draw import polygon2mask

import omero.clients
from omero.gateway import BlitzGateway


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
