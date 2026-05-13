from __future__ import annotations

from pathlib import Path
from typing import Any

from lxml import etree

from metamapper.config import MetadataConfig


def _append_text(parent: etree._Element, tag: str, value: Any) -> etree._Element | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    child = etree.SubElement(parent, tag)
    child.text = str(value)
    return child


def _build_contact(parent: etree._Element, tag: str, contact: dict[str, Any], person_org_mode: str = "person_org") -> None:
    container = etree.SubElement(parent, tag)
    cntinfo = etree.SubElement(container, "cntinfo")

    person = contact.get("person")
    organization = contact.get("organization")
    if person_org_mode == "org_person":
        block = etree.SubElement(cntinfo, "cntorgp")
        _append_text(block, "cntorg", organization)
        _append_text(block, "cntper", person)
    else:
        block = etree.SubElement(cntinfo, "cntperp")
        _append_text(block, "cntper", person)
        _append_text(block, "cntorg", organization)

    _append_text(cntinfo, "cntpos", contact.get("position"))

    if any(contact.get(key) for key in ("address_type", "address", "city", "state", "postal", "country")):
        cntaddr = etree.SubElement(cntinfo, "cntaddr")
        _append_text(cntaddr, "addrtype", contact.get("address_type", "mailing"))
        address_value = contact.get("address")
        if isinstance(address_value, list):
            for line in address_value:
                _append_text(cntaddr, "address", line)
        else:
            _append_text(cntaddr, "address", address_value)
        _append_text(cntaddr, "city", contact.get("city"))
        _append_text(cntaddr, "state", contact.get("state"))
        _append_text(cntaddr, "postal", contact.get("postal"))
        _append_text(cntaddr, "country", contact.get("country"))

    _append_text(cntinfo, "cntvoice", contact.get("phone"))
    _append_text(cntinfo, "cntemail", contact.get("email"))


def build_metadata_xml(config: MetadataConfig) -> etree._ElementTree:
    root = etree.Element("metadata")

    idinfo = etree.SubElement(root, "idinfo")
    citation = etree.SubElement(idinfo, "citation")
    citeinfo = etree.SubElement(citation, "citeinfo")
    citation_data = config.get("citation", {})

    for origin in citation_data.get("originators", []):
        _append_text(citeinfo, "origin", origin)
    _append_text(citeinfo, "pubdate", citation_data.get("publication_date"))
    _append_text(citeinfo, "title", citation_data.get("title"))
    _append_text(citeinfo, "geoform", citation_data.get("geoform", "vector digital data"))

    series = citation_data.get("series") or {}
    if series:
        serinfo = etree.SubElement(citeinfo, "serinfo")
        _append_text(serinfo, "sername", series.get("name"))
        _append_text(serinfo, "issue", series.get("issue"))

    pubinfo_data = citation_data.get("publication_info") or {}
    pubinfo = etree.SubElement(citeinfo, "pubinfo")
    _append_text(pubinfo, "pubplace", pubinfo_data.get("place"))
    _append_text(pubinfo, "publish", pubinfo_data.get("publisher"))

    for link in citation_data.get("online_links", []):
        _append_text(citeinfo, "onlink", link)
    _append_text(citeinfo, "othercit", citation_data.get("other_citation"))

    descript = etree.SubElement(idinfo, "descript")
    description = config.get("description", {})
    _append_text(descript, "abstract", description.get("abstract"))
    _append_text(descript, "purpose", description.get("purpose"))
    _append_text(descript, "supplinf", description.get("supplemental_information"))

    timeperd = etree.SubElement(idinfo, "timeperd")
    timeinfo = etree.SubElement(timeperd, "timeinfo")
    time_period = config.get("time_period", {})
    if time_period.get("single_date"):
        sngdate = etree.SubElement(timeinfo, "sngdate")
        _append_text(sngdate, "caldate", time_period.get("single_date"))
    else:
        rngdates = etree.SubElement(timeinfo, "rngdates")
        _append_text(rngdates, "begdate", time_period.get("begin_date"))
        _append_text(rngdates, "enddate", time_period.get("end_date"))
    _append_text(timeperd, "current", time_period.get("current"))

    status = etree.SubElement(idinfo, "status")
    publication_status = citation_data.get("publication_status", {})
    _append_text(status, "progress", publication_status.get("progress"))
    _append_text(status, "update", publication_status.get("update"))

    spdom = etree.SubElement(idinfo, "spdom")
    bounding = etree.SubElement(spdom, "bounding")
    bounds = config.get("spatial_domain.bounding_coordinates", {})
    _append_text(bounding, "westbc", bounds.get("west"))
    _append_text(bounding, "eastbc", bounds.get("east"))
    _append_text(bounding, "northbc", bounds.get("north"))
    _append_text(bounding, "southbc", bounds.get("south"))

    keywords = etree.SubElement(idinfo, "keywords")
    keyword_data = config.get("keywords", {})
    for theme in keyword_data.get("theme_keywords", []):
        theme_el = etree.SubElement(keywords, "theme")
        _append_text(theme_el, "themekt", theme.get("thesaurus", "None"))
        for keyword in theme.get("keywords", []):
            _append_text(theme_el, "themekey", keyword)
    general_keywords = keyword_data.get("general_keywords", [])
    if general_keywords:
        theme_el = etree.SubElement(keywords, "theme")
        _append_text(theme_el, "themekt", "None")
        for keyword in general_keywords:
            _append_text(theme_el, "themekey", keyword)
    place_keywords = keyword_data.get("place_keywords") or {}
    if place_keywords:
        place_el = etree.SubElement(keywords, "place")
        _append_text(place_el, "placekt", place_keywords.get("thesaurus", "None"))
        for keyword in place_keywords.get("keywords", []):
            _append_text(place_el, "placekey", keyword)

    constraints = config.get("constraints", {})
    _append_text(idinfo, "accconst", constraints.get("access_constraints", "None."))
    _append_text(idinfo, "useconst", constraints.get("use_limitations"))

    point_of_contact = config.get("point_of_contact")
    if point_of_contact:
        _build_contact(idinfo, "ptcontac", point_of_contact)

    _append_text(idinfo, "datacred", config.get("data_credits"))

    dataqual = etree.SubElement(root, "dataqual")
    data_quality = config.get("data_quality", {})
    attracc = etree.SubElement(dataqual, "attracc")
    _append_text(attracc, "attraccr", data_quality.get("attribute_accuracy"))
    _append_text(dataqual, "logic", data_quality.get("logical_consistency"))
    _append_text(dataqual, "complete", data_quality.get("completeness"))
    lineage = etree.SubElement(dataqual, "lineage")
    for process_step in data_quality.get("lineage", {}).get("process_steps", []):
        procstep = etree.SubElement(lineage, "procstep")
        _append_text(procstep, "procdesc", process_step.get("description"))
        _append_text(procstep, "procdate", process_step.get("date"))

    spatial_data_org = config.get("spatial_data_organization") or {}
    if spatial_data_org:
        spdoinfo = etree.SubElement(root, "spdoinfo")
        _append_text(spdoinfo, "direct", spatial_data_org.get("direct_spatial_reference_method"))

    spref = etree.SubElement(root, "spref")
    horizsys = etree.SubElement(spref, "horizsys")
    spatial_reference = config.get("spatial_reference", {})
    reference_type = spatial_reference.get("type")
    if reference_type == "geographic":
        geograph = etree.SubElement(horizsys, "geograph")
        geographic = spatial_reference.get("geographic", {})
        _append_text(geograph, "latres", geographic.get("latitude_resolution"))
        _append_text(geograph, "longres", geographic.get("longitude_resolution"))
        _append_text(geograph, "geogunit", geographic.get("unit"))
    elif reference_type == "utm":
        planar = etree.SubElement(horizsys, "planar")
        gridsys = etree.SubElement(planar, "gridsys")
        _append_text(gridsys, "gridsysn", "Universal Transverse Mercator")
        utm = etree.SubElement(gridsys, "utm")
        _append_text(utm, "utmzone", spatial_reference.get("utm", {}).get("zone"))
        transmer = etree.SubElement(utm, "transmer")
        utm_data = spatial_reference.get("utm", {})
        _append_text(transmer, "sfctrmer", utm_data.get("scale_factor"))
        _append_text(transmer, "longcm", utm_data.get("central_meridian"))
        _append_text(transmer, "latprjo", utm_data.get("latitude_projection_origin"))
        _append_text(transmer, "feast", utm_data.get("false_easting"))
        _append_text(transmer, "fnorth", utm_data.get("false_northing"))
        planci = etree.SubElement(planar, "planci")
        _append_text(planci, "plance", "coordinate pair")
        coordrep = etree.SubElement(planci, "coordrep")
        _append_text(coordrep, "absres", utm_data.get("x_resolution"))
        _append_text(coordrep, "ordres", utm_data.get("y_resolution"))
        _append_text(planci, "plandu", utm_data.get("unit", "meters"))

    geodetic = etree.SubElement(horizsys, "geodetic")
    geodetic_data = spatial_reference.get("geodetic", {})
    _append_text(geodetic, "horizdn", geodetic_data.get("datum"))
    _append_text(geodetic, "ellips", geodetic_data.get("ellipsoid"))
    _append_text(geodetic, "semiaxis", geodetic_data.get("semi_major_axis"))
    _append_text(geodetic, "denflat", geodetic_data.get("denominator_of_flattening"))

    eainfo_data = config.get("entity_attribute_information", {})
    if eainfo_data.get("entities"):
        eainfo = etree.SubElement(root, "eainfo")
        for entity in eainfo_data.get("entities", []):
            detailed = etree.SubElement(eainfo, "detailed")
            enttyp = etree.SubElement(detailed, "enttyp")
            _append_text(enttyp, "enttypl", entity.get("name"))
            _append_text(enttyp, "enttypd", entity.get("description"))
            _append_text(enttyp, "enttypds", entity.get("definition_source"))
            for attribute in entity.get("attributes", []):
                attr = etree.SubElement(detailed, "attr")
                _append_text(attr, "attrlabl", attribute.get("label"))
                _append_text(attr, "attrdef", attribute.get("definition"))
                _append_text(attr, "attrdefs", attribute.get("definition_source"))
                enumerated_domain = attribute.get("enumerated_domain") or []
                if enumerated_domain:
                    for domain_value in enumerated_domain:
                        attrdomv = etree.SubElement(attr, "attrdomv")
                        edom = etree.SubElement(attrdomv, "edom")
                        _append_text(edom, "edomv", domain_value.get("value"))
                        _append_text(edom, "edomvd", domain_value.get("definition"))
                        _append_text(edom, "edomvds", domain_value.get("definition_source"))
                else:
                    attrdomv = etree.SubElement(attr, "attrdomv")
                    _append_text(attrdomv, "udom", attribute.get("unrepresentable_domain", "Unrepresentable domain"))

    distribution = config.get("distribution") or {}
    if distribution:
        distinfo = etree.SubElement(root, "distinfo")
        distributor = distribution.get("distributor")
        if distributor:
            _build_contact(distinfo, "distrib", distributor, person_org_mode="org_person")
        _append_text(distinfo, "distliab", distribution.get("liability"))
        stdorder = etree.SubElement(distinfo, "stdorder")
        digform = etree.SubElement(stdorder, "digform")
        digtinfo = etree.SubElement(digform, "digtinfo")
        _append_text(digtinfo, "formname", "Digital Data")
        if distribution.get("online_resource"):
            digtopt = etree.SubElement(digform, "digtopt")
            onlinopt = etree.SubElement(digtopt, "onlinopt")
            computer = etree.SubElement(onlinopt, "computer")
            networka = etree.SubElement(computer, "networka")
            _append_text(networka, "networkr", distribution.get("online_resource"))
        _append_text(stdorder, "fees", distribution.get("fees", "None."))

    metainfo = etree.SubElement(root, "metainfo")
    metadata = config.get("metadata", {})
    _append_text(metainfo, "metd", metadata.get("date"))
    if metadata.get("contact"):
        _build_contact(metainfo, "metc", metadata.get("contact"))
    _append_text(
        metainfo,
        "metstdn",
        metadata.get("standard_name", "FGDC Content Standard for Digital Geospatial Metadata"),
    )
    _append_text(metainfo, "metstdv", metadata.get("standard_version", "FGDC-STD-001-1998"))

    return etree.ElementTree(root)


def write_metadata_xml(tree: etree._ElementTree, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(
        str(path),
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8",
    )
    return path
