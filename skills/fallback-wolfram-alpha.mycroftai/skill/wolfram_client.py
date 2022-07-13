# Copyright 2021 Mycroft AI Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import requests
from mycroft.api import Api
from mycroft.util.log import LOG
from requests import HTTPError

from .ddg_image_search import search_ddg_images
from .util import (
    get_from_nested_dict,
    get_image_file_from_wikipedia_url,
    remove_nested_parentheses,
    save_image,
)


class WolframAlphaClient:
    """Wrapper for multiple WolframAlpha API endpoints."""

    def __init__(self, cache_dir=None, app_id=None) -> None:
        self.cache_dir = cache_dir
        # self.image_path = self.cache_dir

        # Different Wolfram scanners provide different data
        # This is an attempt to split them between those that should be
        # presented with a picture, vs those that should only be text.
        self.scanners_with_pics = ["Data"]
        self.scanners_for_equations = ["Simplification"]
        self.scanners_for_conversion = ["Identity", "ChemicalQuantity"]

        self.spoken_api = WolframSpokenApi(app_id)
        self.v2_api = WolframV2Api(cache_dir, app_id)

    def get_spoken_answer(self, *args, **kwargs):
        """Get speakable answer to a query."""
        return self.spoken_api.get_spoken_answer(*args, **kwargs)

    def get_visual_answer(self, *args, **kwargs):
        """Get visual answer to a query."""
        title = None
        image = None
        data = self.v2_api.get_visual(*args, **kwargs)

        if not (data and data.get("pods")):
            return None, None

        # Map pods by ID to reduce looping over data['pods'] list
        pods = dict()
        primary_answer_pod = None
        for pod in data["pods"]:
            pods[pod["id"]] = pod

        if len(data["pods"]) > 1:
            # index 0 is Input Interpretation
            primary_answer_pod = data["pods"][1]
            LOG.error(primary_answer_pod.get("scanner"))
            # Return equation for specific types of queries
            if (
                primary_answer_pod
                and primary_answer_pod.get("scanner") in self.scanners_for_equations
            ):
                title = self._generate_equation_answer(pods, primary_answer_pod)
            # Return text answer only for specific types of queries
            elif (
                primary_answer_pod
                and primary_answer_pod.get("scanner") in self.scanners_for_conversion
            ):
                title = self._generate_text_only_answer(pods, primary_answer_pod)
            if title is not None:
                return title, None

        title = self._get_title_of_answer(pods)
        image = self._get_image_from_answer(pods, primary_answer_pod, title)

        return title, image

    def _get_image_from_answer(self, pods: dict, primary_pod: dict, title: str) -> str:
        """Download a valid image in a visual answer to local cache.

        Args:
            pods: Dict of all pods keyed by Pod ID.
            primary_pod: The first pod returned after the Input Interpretation.
            title: Expected title of answer used for fallback image search.

        Returns:
            File path of image.
        """
        # the image fetch is causing issues so for now
        # we disable it and force the wolfram alpha png
        image = "/opt/mycroft/skills/fallback-wolfram-alpha.mycroftai/ui/wolfy.png"
        return image

        image = None
        # If a 3rd party imagesource exists, see if it's actually an image
        # Some of these are perfect, others are html pages containing an image
        image_url = get_from_nested_dict(pods, "imagesource")
        if image_url and "wikipedia.org/wiki/File:" in image_url:
            image_url = get_image_file_from_wikipedia_url(image_url)
            LOG.info(f"Image: {image_url}")
            image = save_image(image_url, self.cache_dir)
        if image is None:
            image = search_ddg_images(title, self.cache_dir)
        return image

    def _generate_equation_answer(self, pods: dict, primary_pod: dict) -> str:
        """Generate a short textual representation of a visual answer.

        Args:
            pods: Dict of all pods keyed by Pod ID.
            primary_pod: The first pod returned after the Input Interpretation.
        """
        question = get_from_nested_dict(pods["Input"], "plaintext")
        answer = get_from_nested_dict(primary_pod, "plaintext")
        title = f"{question} = {answer}"
        return title

    def _generate_text_only_answer(self, pods: dict, primary_pod: dict) -> str:
        """Generate a short textual representation of a visual answer.

        Args:
            pods: Dict of all pods keyed by Pod ID.
            primary_pod: The first pod returned after the Input Interpretation.
        """
        answer = get_from_nested_dict(primary_pod, "plaintext")
        clean_answer = remove_nested_parentheses(answer)
        return clean_answer

    def _get_title_of_answer(self, pods: dict) -> str:
        """Extract a title from a visual answer.

        1. Prioritises any 'Result' pod.
        2. Then the Input Interpretation pod
        3. Fallback to the first plaintext answer in any pod.

        Args:
            pods: Dict of all pods keyed by Pod ID.
            primary_pod: The first pod returned after the Input Interpretation.
        """
        if pods.get("Result"):
            title = get_from_nested_dict(pods["Result"], "plaintext")
        else:
            title = get_from_nested_dict(pods["Input"], "plaintext")
        if not title:
            title = get_from_nested_dict(pods, "plaintext")

        clean_title = remove_nested_parentheses(title)
        return clean_title.title()

    def _log_all_response_data(self, data: dict):
        """For debugging only - prints all Wolfram response data.

        This includes the pod info.
        """
        for key in data.keys():
            print(key)
            print(data[key])
            print("")

    def _log_pod_info(self, data: dict):
        """For debugging only - prints all pod info."""
        for idx, pod in enumerate(data["pods"]):
            print(f"{idx}. {pod['id'].upper()}")
            print(f"- Scanner: {pod['scanner']}")
            for item in pod:
                print(f"{item}: {pod[item]}")
                print("")
            print("------------")
            print("")


class WolframV2Api(Api):
    """Wrapper for the WolframAlpha Full Results v2 API.

    https://products.wolframalpha.com/api/documentation/

    Pods of interest
    - Input interpretation - Wolfram's determination of what is being asked about.
    - Name - primary name of
    """

    def __init__(self, cache_dir, app_id=None):
        super(WolframV2Api, self).__init__("wolframAlphaFull")
        self.cache_dir = cache_dir
        self.app_id = app_id

    def send_request(self, params: dict):
        """Send a request to the API.

        If an app_id aka API key has been supplied, a direct request to
        Wolfram Alpha will be made. Otherwise the request will be proxied
        through Mycroft's backend.
        """
        if self.app_id is None:
            return self.request(params)
        else:
            return self.request_direct(params)

    def get_visual(self, query, lat_lon, units="metric", optional_params: dict = {}):
        """Get a graphic based answer to a query."""
        params = {
            "query": {
                "input": query,
                "geolocation": "{},{}".format(*lat_lon),
                "units": units,
                "mode": "Default",
                "format": "image,plaintext",
                "output": "json",
                **optional_params,
            }
        }
        try:
            response = self.send_request(params)
        except HTTPError as err:
            if err.response.status_code == 401:
                raise
            else:
                LOG.exception(err)
                return None
        return response.get("queryresult")

    def request_direct(self, params):
        """Send a request directly to the Wolfram Alpha Endpoint.

        Requires the client be initialized with an API key.
        """
        params = params["query"]
        params["appid"] = self.app_id
        url = "http://api.wolframalpha.com/v2/query"
        response = requests.get(url, params)
        return response.json()


class WolframSpokenApi(Api):
    """Wrapper for the WolframAlpha Spoken API."""

    def __init__(self, app_id=None):
        super(WolframSpokenApi, self).__init__("wolframAlphaSpoken")
        self.app_id = app_id

    def send_request(self, params: dict):
        """Send a request to the API.

        If an app_id aka API key has been supplied, a direct request to
        Wolfram Alpha will be made. Otherwise the request will be proxied
        through Mycroft's backend.
        """
        if self.app_id is None:
            return self.request(params)
        else:
            return self.request_direct(params)

    def get_spoken_answer(self, query, lat_lon, units="metric"):
        """Get answer as short speakable string."""
        params = {
            "query": {
                "i": query,
                "geolocation": "{},{}".format(*lat_lon),
                "units": units,
            }
        }
        try:
            response = self.send_request(params)
        except HTTPError as err:
            status_code = err.response.status_code
            if status_code == 401:
                raise
            elif status_code == 501:
                # TODO - work out why we are getting 501's from Mycroft backend.
                LOG.info("No answer available from Wolfram Alpha.")
                return None
            else:
                LOG.exception(err)
                LOG.error("HTTP response status code: %i" % (status_code))
                return None
        return response

    def request_direct(self, params):
        """Send a request directly to the Wolfram Alpha Endpoint.

        Requires the client be initialized with an API key.
        """
        params = params["query"]
        params["appid"] = self.app_id
        url = "http://api.wolframalpha.com/v1/spoken"
        response = requests.get(url, params)
        return response.text
