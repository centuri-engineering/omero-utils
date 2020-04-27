import io
import base64
import numpy as np

from skimage.draw import polygon2mask, polygon_perimeter
import omero
import imageio
from omero.rtypes import rint, rstring


def get_roi_thumb(conn, image, roi, z=None, t=None, c=None, draw_roi=True):
    """Returns a numpy array with the region around the roi image

    For now only shape ROIs are supported

    Parameters
    ----------
    conn : a BlitzGateway connection to an omero database
    image : an  `omero.gateway.ImageWrapper` object
    roi : an omero `omero.gateway.RoiWrapper` object
    z : int
        the Z plane (defaults to the central plane)
    t : int
        the time point (defaults to the midle of the sequence)
    c : int or list of ints
        the channel(s) (defaults to the first 3 colors)
    draw_roi : bool, default True
        whether to draw the ROI shape
    """
    if not conn.isConnected():
        conn.connect()
    pixels = image.getPrimaryPixels()
    if z is None:
        z = pixels.sizeZ // 2
    if t is None:
        t = pixels.sizeT // 2

    roi = get_roi_as_arrays(roi)[0].astype(int)
    x, y = (roi.min(axis=0).astype(int) - 1).clip(min=0)
    width, height = (np.ptp(roi, axis=0) - 1).astype(int)

    tile = x, y, width, height
    if c is None:
        tiles = pixels.getTiles([(z, i, t, tile) for i in range(min(pixels.sizeC, 3))])
    elif isinstance(c, list):
        tiles = pixels.getTiles([(z, i, t, tile) for i in c])
    elif isinstance(c, int):
        tiles = pixels.getTile((z, c, t, tile))

    thumb = (
        np.concatenate(list(tiles))
        .reshape((-1, height, width))
        .swapaxes(0, -1)
        .swapaxes(0, 1)
    )
    if draw_roi:
        max_int = image.getPixelRange()[1]
        shifted = (roi - np.array([x + 3, y + 3])[None, :]).clip(min=0)
        coords = polygon_perimeter(shifted[:, 0], shifted[:, 1])
        thumb[coords[1], coords[0]] = max_int

    return thumb


def html_thumb(thumb):
    """Returns an HTML
    """
    with io.BytesIO() as out:
        imageio.imwrite(out, thumb, format="PNG")
        out.seek(0)
        thumb = base64.b64encode(out.read()).decode("utf-8")

    return f"""<img style="width: 200px; max-height: 200px" src="data:image/png;base64,{thumb}">"""


def get_rois_as_labels(image, conn):
    """
    Parameters
    ----------
    image : omero `Image` obect
    conn : connection to the omero DB

    Returns
    -------
    labels : `np.ndarray` with the image shape

    """

    imshape = (image.getSizeX(), image.getSizeY())

    roi_service = conn.getRoiService()
    rois = roi_service.findByImage(image.getId(), None, conn.SERVICE_OPTS).rois
    labels = np.zeros(imshape)
    for i, roi in enumerate(rois):
        for u in range(roi.sizeOfShapes()):
            shape = roi.getShape(u)
            labels += mask_from_polyon_shape(shape, imshape) * (i + 1)

    return labels


def get_roi_as_arrays(roi):
    roi_arrays = []
    for u in range(roi.sizeOfShapes()):
        shape = roi.getShape(u)
        roi_arrays.append(
            np.array(
                [
                    [float(v) for v in l.split(",") if v]
                    for l in shape.getPoints().val.split(" ")
                ]
            )
        )
    return roi_arrays


def mask_from_polyon_shape(shape, imshape):
    """Converts an omero roi `shape` (as returned by the `roi.getShape` method)
    to a binay image with the pixels inside the shape set to 1.

    Parameters
    ----------
    shape : `omero.model.PolygonI` instance
    imshape : tuple, the shape of the output mask

    Returns
    -------
    mask : `np.ndarray` of shape `imshape` and dtype uint8 with ones inside the
       input shape.

    """

    points = shape.getPoints()

    points = np.array(
        [[float(v) for v in l.split(",") if v] for l in points.val.split(" ")]
    )
    return polygon2mask(imshape, points).astype(np.uint8)


def polygon_to_shape(polygon, z=0, t=0, c=0):
    """Creates an omero roi shape from an ndarray polygon instance

    Parameters
    ----------

    polygon : np.ndarray with shape (N, 2)
        where N is the number of points in the polygon
    z, c, t : ints
        the Z, C and T position of the shape in the stack

    """

    shape = omero.model.PolygonI()
    shape.theZ = rint(z)
    shape.theT = rint(t)
    shape.theC = rint(c)
    shape.points = rstring(", ".join((f"{int(p[0])},{int(p[1])}" for p in polygon)))
    return shape


def register_shape_to_roi(image, polygon, conn, roi=None, z=0, t=0, c=0):
    """Adds a polygon shape to an omero ROI. If no roi is provided,
    creates it first.

    Parameters
    ----------
    image : omero Image object
    polygon : np.ndarray of shape (N, 2)
    conn : connection to the omero db
    roi : omero ROI, default None
       if it is None, a new ROI will be created
    z, t, c : position of the ROI in the stack (defaults to 0)


    Returns
    -------
    roi: the roi

    """

    updateService = conn.getUpdateService()
    if roi is None:
        # create an ROI, link it to Image
        roi = omero.model.RoiI()
        # use the omero.model.ImageI that underlies the 'image' wrapper
        roi.setImage(image._obj)

    shape = polygon_to_shape(polygon, z=z, t=t, c=c)
    roi.addShape(shape)
    # Save the ROI (saves any linked shapes too)
    return updateService.saveAndReturnObject(roi)
