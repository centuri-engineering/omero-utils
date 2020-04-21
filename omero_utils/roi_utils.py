import numpy as np

from skimage.draw import polygon2mask
import omero
from omero.rtypes import rint, rstring


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
    rois = roi_service.findByImage(image.getId(), None).rois
    labels = np.zeros(imshape)
    for i, roi in enumerate(rois):
        for u in range(roi.sizeOfShapes()):
            shape = roi.getShape(u)
            labels += mask_from_polyon_shape(shape, imshape) * (i + 1)

    return labels


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
