"""
XML adapter: Orbit Ephemeris Message reader.

OEM/XML structure (§8.10):

  <oem id="CCSDS_OEM_VERS" version="3.0">
    <header> ... </header>
    <body>
      <segment>+                          (one or more)
        <metadata> ... </metadata>
        <data>
          <stateVector>+                  (one per ephemeris epoch, §8.10.13)
            <EPOCH>...</EPOCH>
            <X units="km">...</X>
            ...
          </stateVector>
          <covarianceMatrix>*             (zero or more, §8.10.19)
            <EPOCH>...</EPOCH>
            <COV_REF_FRAME>...</COV_REF_FRAME>
            <CX_X units="km**2">...</CX_X>
            ...
          </covarianceMatrix>
        </data>
      </segment>
    </body>
  </oem>

§8.1    — ODM keyword elements use all-caps names.
§8.10.13 — <stateVector> wraps one ephemeris data line.
§8.10.19 — <covarianceMatrix> wraps one covariance matrix epoch.
"""
from __future__ import annotations

from pathlib import Path

from orbit_data_messages.io.xml._utils import read_model
from orbit_data_messages.io.xml.parser import find_all
from orbit_data_messages.io.xml.parser import find_child
from orbit_data_messages.io.xml.parser import parse_xml_file
from orbit_data_messages.io.xml.parser import strip_ns
from orbit_data_messages.models.oem import OEM

_STATE_VECTOR     = "stateVector"
_COV_MATRIX       = "covarianceMatrix"


class XMLOEMReader:
    """
    Reads an OEM/XML file and returns a validated OEM domain model.

    Satisfies MessageReaderPort structurally.
    """

    def read(self, path: Path) -> OEM:
        """Reads an XML OEM file and returns a validated OEM domain model.

        Args:
            path: Path to the XML OEM file.

        Returns:
            A fully validated OEM domain model. Pydantic ValidationError is
            never swallowed — it propagates to the caller unchanged.
        """
        root = parse_xml_file(path)
        version = root.attrib.get("version", "2.0")

        header_el  = find_child(root, "header")
        body_el    = find_child(root, "body")

        header = OEM.Header(**read_model(
            header_el, OEM.Header,
            extra_kvs={"CCSDS_OEM_VERS": version},
        ))

        segments: list[OEM.Segment] = []
        for segment_el in find_all(body_el, "segment"):
            metadata_el = find_child(segment_el, "metadata")
            data_el     = find_child(segment_el, "data")

            metadata = OEM.Segment.Metadata(**read_model(metadata_el, OEM.Segment.Metadata))

            # §7.8.9 — collect <COMMENT> elements that precede the first
            # <stateVector> for EphemerisData.comment, and those that precede
            # the first <covarianceMatrix> (after the stateVectors) for
            # CovarianceMatrix.comment.
            ephem_comments: list[str] = []
            cov_comments:   list[str] = []
            phase = "ephem"   # 'ephem' → before stateVectors; 'cov' → between SV/COV

            for child in data_el:
                tag = strip_ns(child.tag)
                if tag == _STATE_VECTOR:
                    phase = "cov"
                elif tag == _COV_MATRIX:
                    break
                elif tag == "COMMENT":
                    if phase == "ephem":
                        ephem_comments.append((child.text or "").strip())
                    else:
                        cov_comments.append((child.text or "").strip())

            # §8.10.13 — one <stateVector> per ephemeris epoch.
            sv_lines = [
                OEM.Segment.EphemerisData.EphemerisDataLine(
                    **read_model(sv_el, OEM.Segment.EphemerisData.EphemerisDataLine)
                )
                for sv_el in find_all(data_el, _STATE_VECTOR)
            ]
            ephemeris_data = OEM.Segment.EphemerisData(
                comment=ephem_comments or None,
                ephemeris_data_lines=sv_lines,
            )

            # §8.10.19 — zero or more <covarianceMatrix> elements.
            cml_list = [
                OEM.Segment.CovarianceMatrix.CovarianceMatrixLines(
                    **read_model(cov_el, OEM.Segment.CovarianceMatrix.CovarianceMatrixLines)
                )
                for cov_el in find_all(data_el, _COV_MATRIX)
            ]
            covariance_matrix = (
                OEM.Segment.CovarianceMatrix(
                    comment=cov_comments or None,
                    covariance_matrix_lines=cml_list,
                )
                if cml_list else None
            )

            segments.append(OEM.Segment(
                metadata=metadata,
                ephemeris_data=ephemeris_data,
                covariance_matrix=covariance_matrix,
            ))

        return OEM(header=header, segments=segments)


OrbitEphemerisMessageXMLReader = XMLOEMReader
