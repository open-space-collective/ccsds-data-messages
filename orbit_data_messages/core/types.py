from .omm import OMM
from .oem import OEM
from .opm import OPM
from .ocm import OCM


CCSDSDataMessage = OMM | OEM | OPM | OCM
