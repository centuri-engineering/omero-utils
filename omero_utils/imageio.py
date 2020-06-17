import numpy as np
from itertools import product


class ImageReader:
    """Abstract class defining an image reader for the metrology
    platform
    """

    minimal_metadata = {
        "SizeX": 1,
        "SizeY": 1,
        "SizeZ": 1,
        "SizeC": 1,
        "SizeT": 1,
        "Id": 0,
        "AquisitionDate": "2000-01-01T00:00:00",
        "LensNA": 1.0,
        "PhysicalSizeX": 1.0,
        "nominalMagnification": 10.0,
        "ChannelLabels": ["R", "G", "B"],
    }

    def __init__(self, image=None):

        self.image = image
        self.id = 0
        self.metadata = self.get_metadata()

    def __enter__(self):
        return self

    def get_metadata(self):
        return self.minimal_metadata

    def get_plane(self, c, z, t):
        raise NotImplementedError

    def __iter__(self):
        size_c = self.metadata["SizeC"]
        size_z = self.metadata["SizeZ"]
        size_t = self.metadata["SizeT"]
        for czt in product(range(size_c), range(size_z), range(size_t)):
            yield czt, self.get_plane(*czt)

    def __exit__(self, exc_type, exc_value, traceback):
        raise NotImplementedError


class OmeroImageReader(ImageReader):
    """Image reader interface for an OMERO data base

    Attributes
    ----------
    id : int, the image Id
    conn : a `BlitzGateway` connection
    image : the OMERO Image object
    pixels : the OMERO Pixels object


    """

    def __init__(self, image_id=None, conn=None):
        """Creates and OmeroImageReader instance.

        Parameters
        ----------
        image_id : int
            The image identifier in the omero database
        conn :
            A BlitzGateway connection instance (will be connected at instanciation)

        Usage
        -----
        Please use the context manager to ensure connection is closed
        on exiting the reader:

        .. code-block:: python
            with imageio.OmeroImageReader(im_id, conn) as image_reader:
                do_something
            # conn is closed outside of the context manager

        Note
        ----

        This interface implements an iterator over the image stack:
        .. code-block:: python
            with imageio.OmeroImageReader(im_id, conn) as image_reader:
                for (c, z, t), plane in image_reader:
                    print(f"This is image from channel {c}, z-slice {z} and time point {t}")
                    # plane is a numpy 2D array

            # conn is closed outside of the context manager



        """
        print(f"Treating {image_id}")
        self.id = image_id
        self.conn = conn
        self.conn.connect()
        self.conn.SERVICE_OPTS.setOmeroGroup("-1")
        self.image = conn.getObject("Image", oid=image_id)
        self.pixels = self.image.getPrimaryPixels()
        super().__init__(self.image)

    def __enter__(self):
        return self

    def get_metadata(self):
        """Returns a dictionnary with the image metadata
        with keys:

        * "SizeZ"
        * "SizeC"
        * "SizeT"
        * "Id"
        * "AquisitionDate"
        * "PhysicalSizeX"
        * "ChannelLabels"
        * "LensNA"
        * "nominalMagnification"

        The last two keys are set only if `self.image.getObjectiveSettings()`
        returns an `ObjectiveSettings` instance.

        See Also
        --------
        https://docs.openmicroscopy.org/omero-blitz/5.5.5/slice2html/omero/model/Image.html

        """
        obj_settings = self.image.getObjectiveSettings()
        if not obj_settings:
            print("No objective found")
            obj = None
        else:
            obj = obj_settings.getObjective()

        sizex = self.pixels.getPhysicalSizeX()
        metadata = {
            "SizeZ": self.image.getSizeZ(),
            "SizeC": self.image.getSizeC(),
            "SizeT": self.image.getSizeT(),
            "Id": self.image.getId(),
            "AquisitionDate": self.image.getAcquisitionDate(),
            "PhysicalSizeX": sizex.getValue(),
            "ChannelLabels": self.image.getChannelLabels(),
        }
        if obj:
            metadata.update(
                {
                    "LensNA": obj.getLensNA(),
                    "nominalMagnification": obj.getnominalMagnification(),
                }
            )
        else:
            metadata.update(
                {"LensNA": np.nan, "nominalMagnification": np.nan,}
            )

        return metadata

    def get_plane(self, c, z, t):
        return self.pixels.getPlane(theC=c, theZ=z, theT=t)

    def __exit__(self, exc_type, exc_value, traceback):
        self.conn.close()
