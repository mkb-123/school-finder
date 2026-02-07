"""Government data services for fetching real school data.

This package provides services that fetch data from official UK government
sources instead of relying on static seed files or generated data.

Available services:
- GIASService: School register data from Get Information About Schools
- OfstedService: Inspection ratings from Ofsted management information
- EESService: Performance, admissions, absence & SEND data from Explore Education Statistics API
"""

from src.services.gov_data.ees import EESService
from src.services.gov_data.gias import GIASService
from src.services.gov_data.ofsted import OfstedService

__all__ = ["GIASService", "OfstedService", "EESService"]
