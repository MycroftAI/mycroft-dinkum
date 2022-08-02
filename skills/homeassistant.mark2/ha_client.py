"""
Home Assistant Client
Handle connection between skill and HA instance trough websocket.
"""
import ipaddress
import json
import re

from fuzzywuzzy import fuzz
from requests import get, post
from requests.exceptions import RequestException, Timeout
from requests.models import Response

__author__ = "btotharye"

# Timeout time for HA requests
TIMEOUT = 10

"""Regex for IP address check"""
IP_REGEX = r"".join(
    r"\b(?:https?://)?((?:(?:www\.)?(?:[\da-z\.-]+)\.(?:[a-z]{2,6})|"
    r"(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2["
    r"0-4][0-9]|[01]?[0-9][0-9]?)|(?:(?:[0-9a-fA-F]{1,4}:){7,7}[0-9a"
    r"-fA-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,7}:|(?:[0-9a-fA-F]{1,4}:){"
    r"1,6}:[0-9a-fA-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,5}(?::[0-9a-fA-F"
    r"]{1,4}){1,2}|(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1"
    r",3}|(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}|(?:[0"
    r"-9a-fA-F]{1,4}:){1,2}(?::[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,"
    r"4}:(?:(?::[0-9a-fA-F]{1,4}){1,6})|:(?:(?::[0-9a-fA-F]{1,4}){1,"
    r"7}|:)|fe80:(?::[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(?:fff"
    r"f(?::0{1,4}){0,1}:){0,1}(?:(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0"
    r",1}[0-9])\.){3,3}(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])|"
    r"(?:[0-9a-fA-F]{1,4}:){1,4}:(?:(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]"
    r"){0,1}[0-9])\.){3,3}(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9"
    r"]))))(?::[0-9]{1,4}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{"
    r"2}|655[0-2][0-9]|6553[0-5])?(?:/[\w\.-]*)*/?\b"
)

IPV6_REGEX = r"".join(
    r"((?:[0-9a-fA-F]{1,4}:){1,4}:(?:(?:25[0-5]|(?:2[0-4]|1{0,1}[0"
    r"-9]){0,1}[0-9])\.){3,3}(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1"
    r"}[0-9])|(?:fe80:(?::[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,})|"
    r"::(?:ffff(?::0{1,4}){0,1}:){0,1}(?:(?:25[0-5]|(2[0-4]|1{0,1}"
    r"[0-9]){0,1}[0-9])\.){3,3}(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0"
    r",1}[0-9])|(?:(?:[0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4})|(?:"
    r"[0-9a-fA-F]{1,4}:){1,7}(?:(?::[0-9a-fA-F]{1,4}){1,7}|:)|(?::"
    r":(?:[0-9a-fA-F]{1,4}:){,6}(?:[0-9a-fA-F]{1,4})))"
)


def check_url(ip_address: str) -> str:
    """Function to check if valid url/ip was supplied

    First regex check for IPv6.
    If nothing found, second regex try to find IPv4 and domains names.

    Args:
        ip_address: String with ip address set by user.

    Returns:
        Ip address found by regex.
    """
    if not ip_address:
        return

    valid = False
    matches = re.findall(IPV6_REGEX, ip_address)
    if matches:
        largest = max(matches, key=len)[0]

        if ":" in largest:
            try:
                checked_ip = ipaddress.ip_address(largest)
                if checked_ip:
                    valid = True
            except ValueError:
                return None

            if largest and valid:
                return largest

    matches = re.search(IP_REGEX, ip_address)
    if matches:
        return matches.group(1)
    return None


# pylint: disable=R0912, W0105, W0511
class HomeAssistantClient:
    """Home Assistant client class"""

    def __init__(self, config):
        self.ssl = config["ssl"] or False
        self.verify = config["verify"] or True
        ip_address = config["ip_address"]
        token = config["token"]
        port_number = config["port_number"]
        if self.ssl:
            self.url = f"https://{ip_address}"
        else:
            self.url = f"http://{ip_address}"
        if port_number:
            self.url = f"{self.url}:{port_number}"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _get_state(self) -> json:
        """Get state object

        Throws request Exceptions
        (Subclasses of ConnectionError or RequestException,
          raises HTTPErrors if non-Ok status code)

        Returns:
            Json containing response from HA.
        """
        if self.ssl:
            req = get(
                f"{self.url}/api/states",
                headers=self.headers,
                verify=self.verify,
                timeout=TIMEOUT,
            )
        else:
            req = get(f"{self.url}/api/states", headers=self.headers, timeout=TIMEOUT)
        req.raise_for_status()
        return req.json()

    def connected(self) -> bool:
        """Simple connection test to HA instance

        Returns:
            Return false if any of errors occur
        """
        try:
            self._get_state()
            return True
        except (Timeout, ConnectionError, RequestException):
            return False

    def find_entity(self, entity: str, types: list) -> dict:
        """Find entity with specified name, fuzzy matching

        Throws request Exceptions
        (Subclasses of ConnectionError or RequestException,
          raises HTTPErrors if non-Ok status code)

        Returns:
            Dict represeting entity
        """
        json_data = self._get_state()
        # require a score above 50%
        best_score = 50
        best_entity = None
        if json_data:
            for state in json_data:
                try:
                    if state["entity_id"].split(".")[0] in types:
                        # something like temperature outside
                        # should score on "outside temperature sensor"
                        # and repetitions should not count on my behalf
                        score = fuzz.token_sort_ratio(
                            entity, state["attributes"]["friendly_name"].lower()
                        )
                        if score > best_score:
                            best_score = score
                            best_entity = {
                                "id": state["entity_id"],
                                "dev_name": state["attributes"]["friendly_name"],
                                "state": state["state"],
                                "best_score": best_score,
                                "attributes": state["attributes"],
                            }
                        score = fuzz.token_sort_ratio(
                            entity, state["entity_id"].lower()
                        )
                        if score > best_score:
                            best_score = score
                            best_entity = {
                                "id": state["entity_id"],
                                "dev_name": state["attributes"]["friendly_name"],
                                "state": state["state"],
                                "best_score": best_score,
                                "attributes": state["attributes"],
                            }
                except KeyError:
                    pass
        return best_entity

    def find_entity_attr(self, entity: str) -> dict:
        """Get the entity attributes to be used in the response dialog.

        Throws request Exceptions
        (Subclasses of ConnectionError or RequestException,
          raises HTTPErrors if non-Ok status code)

        Returns:
            Dict with entity's attributes
        """
        json_data = self._get_state()

        if json_data:
            for attr in json_data:
                if attr["entity_id"] == entity:
                    entity_attrs = attr["attributes"]
                    try:
                        if attr["entity_id"].startswith("light."):
                            # Not all lamps do have a color
                            unit_measur = entity_attrs["brightness"]
                        else:
                            unit_measur = entity_attrs["unit_of_measurement"]
                    except KeyError:
                        unit_measur = ""
                    # IDEA: return the color if available
                    # TODO: change to return the whole attr dictionary =>
                    # free use within handle methods
                    sensor_name = entity_attrs["friendly_name"]
                    sensor_state = attr["state"]
                    entity_attr = {
                        "unit_measure": unit_measur,
                        "name": sensor_name,
                        "state": sensor_state,
                    }
                    return entity_attr
        return None

    def list_entities(self, types: list) -> list:
        """List all entities matching domains used within our skill

        Throws request Exceptions
        (Subclasses of ConnectionError or RequestException,
          raises HTTPErrors if non-Ok status code)

        Returns:
            List with entity and it's friendly name
        """

        json_data = self._get_state()
        entities = []
        if json_data:
            for state in json_data:
                try:
                    entity_id = state["entity_id"].split(".")
                    domain = entity_id[0]
                    entity = entity_id[1]
                    if domain in types:
                        """Domain of Entity is in handled types.
                        Add Entity and its friendly name to list.
                        """
                        entities.append(entity)
                        entities.append(state["attributes"]["friendly_name"].lower())
                except KeyError:
                    pass
        return entities

    def execute_service(self, domain: str, service: str, data: dict) -> Response:
        """Execute service at HAServer

        Throws request Exceptions
        (Subclasses of ConnectionError or RequestException,
          raises HTTPErrors if non-Ok status code)

        Returns:
            HA response
        """
        if self.ssl:
            req = post(
                f"{self.url}/api/services/{domain}/{service}",
                headers=self.headers,
                data=json.dumps(data),
                verify=self.verify,
                timeout=TIMEOUT,
            )
        else:
            req = post(
                f"{self.url}/api/services/{domain}/{service}",
                headers=self.headers,
                data=json.dumps(data),
                timeout=TIMEOUT,
            )
        req.raise_for_status()
        return req

    def find_component(self, component: str) -> bool:
        """Check if a component is loaded at the HA-Server

        Throws request Exceptions
        (Subclasses of ConnectionError or RequestException,
          raises HTTPErrors if non-Ok status code)

        Returns:
            True/False if component found in response
        """
        if self.ssl:
            req = get(
                f"{self.url}/api/components",
                headers=self.headers,
                verify=self.verify,
                timeout=TIMEOUT,
            )
        else:
            req = get(
                f"{self.url}/api/components", headers=self.headers, timeout=TIMEOUT
            )

        req.raise_for_status()
        return component in req.json()

    def engage_conversation(self, utterance: str) -> dict:
        """Engage the conversation component at the Home Assistant server

        Throws request Exceptions
        (Subclasses of ConnectionError or RequestException,
          raises HTTPErrors if non-Ok status code)
        Attributes:
            utterance    raw text message to be processed

        Returns:
            Dict answer by Home Assistant server
            { 'speech': textual answer,
              'extra_data': ...}
        """
        data = {"text": utterance}
        if self.ssl:
            req = post(
                f"{self.url}/api/conversation/process",
                headers=self.headers,
                data=json.dumps(data),
                verify=self.verify,
                timeout=TIMEOUT,
            )
        else:
            req = post(
                f"{self.url}/api/conversation/process",
                headers=self.headers,
                data=json.dumps(data),
                timeout=TIMEOUT,
            )
        req.raise_for_status()
        return req.json()["speech"]["plain"]
