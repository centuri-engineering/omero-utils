import omero


def get_images_from_instrument(instrument_id, conn):
    """Returns a list of images ids

    Parameters;

    """
    conn.SERVICE_OPTS.setOmeroGroup("-1")
    params = omero.sys.Parameters()
    params.map = {"instrument": rlong(instrument_id)}
    queryService = conn.getQueryService()
    images = queryService.projection(
        "select i.id from Image i where i.instrument.id=:instrument",
        params,
        conn.SERVICE_OPTS,
    )
    return [im[0].val for im in images]
