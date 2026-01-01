import logging
import time
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Iterator,
    List,
    Literal,
    Optional,
)

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .auth import TokenManager
from .exceptions import (
    NinjaRMMAPIError,
    NinjaRMMAuthError,
    NinjaRMMError,
    NinjaRMMValidationError,
)
from .utils import process_api_response

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ninjapy.client")


class NinjaRMMClient:
    """
    Client for interacting with the NinjaRMM API v2.0.9-draft

    This client provides access to the NinjaOne Public API, including functionality for:
    - Organization management
    - Device management
    - Policy management
    - Alert management
    - Custom fields
    - Location management
    """

    API_VERSION = "2.0.9-draft"
    DEFAULT_BASE_URL = "https://api.ninjarmm.com"

    # API Scopes
    SCOPE_MONITORING = "monitoring"
    SCOPE_MANAGEMENT = "management"
    SCOPE_CONTROL = "control"

    # Node Classes (from API spec)
    NODE_CLASS = Literal[
        "WINDOWS_SERVER",
        "WINDOWS_WORKSTATION",
        "LINUX_WORKSTATION",
        "MAC",
        "ANDROID",
        "APPLE_IOS",
        "APPLE_IPADOS",
        "VMWARE_VM_HOST",
        "VMWARE_VM_GUEST",
        "HYPERV_VMM_HOST",
        "HYPERV_VMM_GUEST",
        "LINUX_SERVER",
        "MAC_SERVER",
        "CLOUD_MONITOR_TARGET",
        "NMS_SWITCH",
        "NMS_ROUTER",
        "NMS_FIREWALL",
        "NMS_PRIVATE_NETWORK_GATEWAY",
        "NMS_PRINTER",
        "NMS_SCANNER",
        "NMS_DIAL_MANAGER",
        "NMS_WAP",
        "NMS_IPSLA",
        "NMS_COMPUTER",
        "NMS_VM_HOST",
        "NMS_APPLIANCE",
        "NMS_OTHER",
        "NMS_SERVER",
        "NMS_PHONE",
        "NMS_VIRTUAL_MACHINE",
        "NMS_NETWORK_MANAGEMENT_AGENT",
    ]

    def __init__(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        scope: str,
        base_url: str = "https://app.ninjarmm.com",
        convert_timestamps: bool = True,
        request_timeout: int = 10,
        retry_total: int = 3,
        retry_backoff_factor: float = 1.0,
        retry_status_forcelist: Optional[List[int]] = None,
        rate_limit_default_retry_after: int = 10,
    ) -> None:
        """
        Initialize the NinjaRMM API client.

        Args:
            token_url: OAuth2 token endpoint URL
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret
            scope: OAuth2 scope(s)
            base_url: Base URL for the API. Defaults to https://api.ninjarmm.com
            convert_timestamps: Whether to automatically convert epoch timestamps
                to ISO format. Defaults to True.
            request_timeout: Timeout for HTTP requests in seconds. Defaults to 10.
            retry_total: Total number of retries for failed requests. Defaults to 3.
            retry_backoff_factor: Factor for exponential backoff between retries. Defaults to 1.0.
            retry_status_forcelist: List of HTTP status codes to retry on.
                Defaults to [429, 500, 502, 503, 504].
            rate_limit_default_retry_after: Default retry-after time when rate limited
                and no Retry-After header is provided. Defaults to 10 seconds.
        """
        self.base_url = base_url.rstrip("/")
        self.convert_timestamps = convert_timestamps
        self.request_timeout = request_timeout
        self.retry_total = retry_total
        self.retry_backoff_factor = retry_backoff_factor
        self.retry_status_forcelist = retry_status_forcelist or [
            429,
            500,
            502,
            503,
            504,
        ]
        self.rate_limit_default_retry_after = rate_limit_default_retry_after
        self.token_manager = TokenManager(token_url, client_id, client_secret, scope)
        self.session = requests.Session()
        self.session.headers.update(
            {"Content-Type": "application/json", "Accept": "application/json"}
        )

        # Configure retries with exponential backoff
        retries = Retry(
            total=self.retry_total,
            backoff_factor=self.retry_backoff_factor,
            status_forcelist=self.retry_status_forcelist,
            allowed_methods=[
                "HEAD",
                "GET",
                "OPTIONS",
                "POST",
                "PUT",
                "PATCH",
                "DELETE",
            ],
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _request(
        self,
        method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"],
        endpoint: str,
        **kwargs: Any,
    ) -> Any:
        """
        Make a request to the API.

        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional arguments to pass to requests

        Returns:
            The JSON response from the API

        Raises:
            NinjaRMMAuthError: If authentication fails
            NinjaRMMError: If any other error occurs
        """
        # Ensure endpoint starts with /
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"

        # Get valid token before each request
        token = self.token_manager.get_valid_token()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

        url = f"{self.base_url}{endpoint}"
        logger.info(f"Preparing request: {method} {url} with kwargs: {kwargs}")

        try:
            logger.info("Sending HTTP request now...")
            # Explicitly set a timeout to prevent indefinite hangs
            response = self.session.request(
                method, url, timeout=self.request_timeout, **kwargs
            )
            logger.info(
                f"HTTP request completed with status code: " f"{response.status_code}"
            )

            # Handle rate limiting explicitly
            if response.status_code == 429:
                retry_after = int(
                    response.headers.get(
                        "Retry-After", self.rate_limit_default_retry_after
                    )
                )
                logger.warning(f"Rate limited. Retrying after {retry_after} seconds.")
                time.sleep(retry_after)
                return self._request(method, endpoint, **kwargs)

            response.raise_for_status()

            if response.status_code == 204:
                logger.info("Received 204 No Content response.")
                return None

            logger.info("Parsing JSON response.")
            response_data = response.json()

            # Apply timestamp conversion if enabled
            if self.convert_timestamps:
                response_data = process_api_response(
                    response_data, convert_timestamps=True
                )

            return response_data

        except requests.exceptions.Timeout:
            logger.error("Request timed out.")
            raise NinjaRMMError("Request timed out.")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTPError encountered: {str(e)}")
            try:
                error_data = e.response.json()
                message = error_data.get("message", str(e))
            except ValueError:
                message = str(e)
                error_data = None

            if e.response.status_code == 401:
                raise NinjaRMMAuthError("Authentication failed")
            elif e.response.status_code == 403:
                raise NinjaRMMError("Permission denied")
            elif e.response.status_code == 404:
                raise NinjaRMMError("Resource not found")
            else:
                raise NinjaRMMAPIError(message, e.response.status_code, error_data)

        except requests.exceptions.RequestException as e:
            logger.error(f"RequestException encountered: {str(e)}")
            raise NinjaRMMError(f"Request failed: {str(e)}")

    def get_organizations(
        self,
        page_size: Optional[int] = None,
        after: Optional[int] = None,
        org_filter: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get list of organizations.

        Args:
            page_size: Limit number of organizations to return
            after: Last Organization Identifier from previous page
            org_filter: Organization filter

        Returns:
            List of organization objects
        """
        params = {}
        if page_size is not None:
            params["pageSize"] = page_size
        if after is not None:
            params["after"] = after
        if org_filter:
            params["of"] = org_filter

        return self._request("GET", "/v2/organizations", params=params)

    def get_organizations_detailed(
        self,
        page_size: Optional[int] = None,
        after: Optional[int] = None,
        org_filter: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get list of organizations with detailed information.

        Args:
            page_size: Limit number of organizations to return
            after: Last Organization Identifier from previous page
            org_filter: Organization filter

        Returns:
            List of detailed organization objects including:
            - name: Organization full name
            - description: Organization description
            - userData: Custom attributes
            - nodeApprovalMode: Device approval mode (AUTOMATIC/MANUAL/REJECT)
            - tags: Organization tags
            - fields: Custom fields
            - id: Organization identifier
            - locations: List of locations
        """
        params = {}
        if page_size is not None:
            params["pageSize"] = page_size
        if after is not None:
            params["after"] = after
        if org_filter:
            params["of"] = org_filter

        return self._request("GET", "/v2/organizations-detailed", params=params)

    def create_organization(
        self,
        name: str,
        description: Optional[str] = None,
        template_org_id: Optional[int] = None,
        **kwargs,
    ) -> Dict:
        """
        Create a new organization.

        Args:
            name: Organization full name
            description: Organization description
            template_org_id: Model/Template organization to copy settings from
            **kwargs: Additional organization properties

        Returns:
            Dict: Created organization object

        Raises:
            NinjaRMMAuthError: If authentication fails
            NinjaRMMValidationError: If required fields are missing or invalid
            NinjaRMMAPIError: If organization creation fails
                - 403: Permission denied
                - 404: Template organization not found
                - 409: Organization with name already exists
        """
        data = {"name": name, **kwargs}
        if description:
            data["description"] = description

        params = {}
        if template_org_id:
            params["templateOrganizationId"] = template_org_id

        return self._request("POST", "/v2/organizations", json=data, params=params)

    def approve_devices(self, device_ids: List[int]) -> None:
        """
        Approve devices that are waiting for approval.

        Args:
            device_ids (List[int]): List of device IDs to approve
        """
        data = {"devices": device_ids}
        self._request("POST", "/v2/devices/approval/APPROVE", json=data)

    def reject_devices(self, device_ids: List[int]) -> None:
        """
        Reject devices that are waiting for approval.

        Args:
            device_ids (List[int]): List of device IDs to reject
        """
        data = {"devices": device_ids}
        self._request("POST", "/v2/devices/approval/REJECT", json=data)

    def reset_alert(self, alert_uid: str) -> None:
        """
        Reset an alert/condition by UID.

        Args:
            alert_uid (str): Alert/condition UID
        """
        self._request("DELETE", f"/v2/alert/{alert_uid}")

    def reset_alert_with_data(self, alert_uid: str, activity_data: Dict) -> None:
        """
        Reset an alert/condition and provide custom data for activity.

        Args:
            alert_uid (str): Alert/condition UID
            activity_data (Dict): Custom activity data
        """
        self._request("POST", f"/v2/alert/{alert_uid}/reset", json=activity_data)

    def get_organization(self, org_id: int) -> Dict:
        """
        Get a specific organization by ID.

        Args:
            org_id (int): Organization identifier

        Returns:
            Organization object
        """
        return self._request("GET", f"/v2/organizations/{org_id}")

    def update_organization(
        self,
        org_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        user_data: Optional[Dict[str, Any]] = None,
        node_approval_mode: Optional[str] = None,
        tags: Optional[List[str]] = None,
        fields: Optional[Dict[str, Dict]] = None,
    ) -> Dict:
        """
        Update an organization.

        Args:
            org_id (int): Organization identifier
            name (str, optional): Organization full name
            description (str, optional): Organization description
            user_data (Dict, optional): Custom attributes
            node_approval_mode (str, optional): Device approval mode (AUTOMATIC, MANUAL, REJECT)
            tags (List[str], optional): Tags
            fields (Dict, optional): Custom fields

        Returns:
            Dict: Updated organization details
        """
        # Validate node_approval_mode if provided
        if node_approval_mode and node_approval_mode not in (
            "AUTOMATIC",
            "MANUAL",
            "REJECT",
        ):
            raise NinjaRMMValidationError(
                "Invalid node approval mode. Must be AUTOMATIC, MANUAL, or REJECT",
                "node_approval_mode",
            )

        data: Dict[str, Any] = {}
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description
        if user_data is not None:
            data["userData"] = user_data
        if node_approval_mode is not None:
            data["nodeApprovalMode"] = node_approval_mode
        if tags is not None:
            data["tags"] = tags
        if fields is not None:
            data["fields"] = fields

        return self._request("PATCH", f"/v2/organization/{org_id}", json=data)

    def delete_organization(self, org_id: int) -> None:
        """
        Delete an organization.

        Args:
            org_id: Organization identifier

        Raises:
            NinjaRMMAuthError: If authentication fails
            NinjaRMMAPIError: If deletion fails
                - 403: Permission denied
                - 404: Organization not found
                - 409: Organization has active devices
        """
        self._request("DELETE", f"/v2/organizations/{org_id}")

    def get_organization_settings(self, org_id: int) -> Dict:
        """
        Get organization settings.

        Args:
            org_id (int): Organization identifier

        Returns:
            Organization settings object
        """
        return self._request("GET", f"/v2/organizations/{org_id}/settings")

    def update_organization_settings(self, org_id: int, settings: Dict) -> Dict:
        """
        Update organization settings.

        Args:
            org_id (int): Organization identifier
            settings (Dict): Settings object containing configuration for features like
                           trayicon, splashtop, teamviewer, backup, psa

        Returns:
            Updated organization settings
        """
        return self._request(
            "PUT", f"/v2/organizations/{org_id}/settings", json=settings
        )

    def get_organization_locations(self, org_id: int) -> List[Dict]:
        """
        Get organization locations.

        Args:
            org_id (int): Organization identifier

        Returns:
            List of location objects
        """
        return self._request("GET", f"/v2/organizations/{org_id}/locations")

    def create_organization_location(
        self,
        org_id: int,
        name: str,
        address: Optional[str] = None,
        description: Optional[str] = None,
        **kwargs,
    ) -> Dict:
        """
        Create a new location for an organization.

        Args:
            org_id (int): Organization identifier
            name (str): Location name
            address (str, optional): Location address
            description (str, optional): Location description
            **kwargs: Additional location properties like tags, fields, userData

        Returns:
            Created location object
        """
        data = {"name": name, **kwargs}
        if address:
            data["address"] = address
        if description:
            data["description"] = description

        return self._request("POST", f"/v2/organizations/{org_id}/locations", json=data)

    def update_organization_location(
        self,
        org_id: int,
        location_id: int,
        name: str,
        address: Optional[str] = None,
        description: Optional[str] = None,
        **kwargs,
    ) -> Dict:
        """
        Update an organization location.

        Args:
            org_id (int): Organization identifier
            location_id (int): Location identifier
            name (str): Location name
            address (str, optional): Location address
            description (str, optional): Location description
            **kwargs: Additional location properties like tags, fields, userData

        Returns:
            Updated location object
        """
        data = {"name": name, **kwargs}
        if address:
            data["address"] = address
        if description:
            data["description"] = description

        return self._request(
            "PATCH", f"/v2/organizations/{org_id}/locations/{location_id}", json=data
        )

    def delete_organization_location(self, org_id: int, location_id: int) -> None:
        """
        Delete an organization location.

        Args:
            org_id (int): Organization identifier
            location_id (int): Location identifier
        """
        self._request("DELETE", f"/v2/organizations/{org_id}/locations/{location_id}")

    def get_organization_policies(self, org_id: int) -> List[Dict]:
        """
        Get organization policy mappings.

        Args:
            org_id (int): Organization identifier

        Returns:
            List of policy mapping objects
        """
        return self._request("GET", f"/v2/organizations/{org_id}/policies")

    def update_organization_policies(
        self, org_id: int, policies: List[Dict]
    ) -> List[Dict]:
        """
        Update organization policy mappings.

        Args:
            org_id (int): Organization identifier
            policies (List[Dict]): List of policy mappings containing nodeRoleId and policyId

        Returns:
            Updated list of policy mapping objects
        """
        return self._request(
            "PUT", f"/v2/organizations/{org_id}/policies", json=policies
        )

    def get_devices(
        self,
        page_size: Optional[int] = None,
        after: Optional[int] = None,
        org_filter: Optional[str] = None,
        expand: Optional[str] = None,
        include_backup_usage: bool = False,
    ) -> List[Dict]:
        """
        Get list of devices.

        Args:
            page_size (int, optional): Limit number of devices to return
            after (int, optional): Last Device Identifier from previous page
            org_filter (str, optional): Organization filter
            expand (str, optional): Expand options
            include_backup_usage (bool): Include backup usage information

        Returns:
            List of device objects
        """
        params = {}
        if page_size:
            params["pageSize"] = page_size
        if after:
            params["after"] = after
        if org_filter:
            params["of"] = org_filter
        if expand:
            params["expand"] = expand
        if include_backup_usage:
            params["includeBackupUsage"] = "true"

        return self._request("GET", "/v2/devices", params=params)

    def get_devices_detailed(
        self,
        page_size: Optional[int] = None,
        after: Optional[int] = None,
        org_filter: Optional[str] = None,
        expand: Optional[str] = None,
        include_backup_usage: bool = False,
    ) -> List[Dict]:
        """
        Get detailed list of devices.

        Args:
            page_size (int, optional): Limit number of devices to return
            after (int, optional): Last Device Identifier from previous page
            org_filter (str, optional): Organization filter
            expand (str, optional): Expand options
            include_backup_usage (bool): Include backup usage information

        Returns:
            List of device objects
        """
        params = {}
        if page_size:
            params["pageSize"] = page_size
        if after:
            params["after"] = after
        if org_filter:
            params["of"] = org_filter
        if expand:
            params["expand"] = expand
        if include_backup_usage:
            params["includeBackupUsage"] = "true"

        return self._request("GET", "/v2/devices-detailed", params=params)

    def get_device(
        self,
        device_id: int,
        expand: Optional[str] = None,
        include_backup_usage: bool = False,
    ) -> Dict:
        """
        Get a specific device by ID.

        Args:
            device_id (int): Device identifier
            include_backup_usage (bool): Include backup usage information
            expand (str, optional): Expand options
        Returns:
            Device object
        """
        params = {}
        if include_backup_usage:
            params["includeBackupUsage"] = "true"
        if expand:
            params["expand"] = expand

        return self._request("GET", f"/v2/devices/{device_id}", params=params)

    def update_device(self, device_id: int, **kwargs) -> Dict:
        """
        Update a device.

        Args:
            device_id (int): Device identifier
            **kwargs: Device properties to update (displayName, systemName, nodeRoleId, policyId, etc.)

        Returns:
            Updated device object
        """
        return self._request("PATCH", f"/v2/devices/{device_id}", json=kwargs)

    def delete_device(self, device_id: int) -> None:
        """
        Delete a device.

        Args:
            device_id (int): Device identifier
        """
        self._request("DELETE", f"/v2/devices/{device_id}")

    def search_devices(
        self,
        query: str,
        page_size: Optional[int] = None,
        cursor: Optional[str] = None,
        **kwargs,
    ) -> Dict:
        """
        Search for devices using query string.

        Args:
            query (str): Search query string
            page_size (int, optional): Number of results per page
            cursor (str, optional): Cursor for pagination
            **kwargs: Additional parameters to pass to the API

        Returns:
            Search results containing devices and metadata
        """
        params = {"q": query}
        if page_size:
            params["pageSize"] = str(page_size)
        if cursor:
            params["cursor"] = cursor
        params.update(kwargs)

        return self._request("GET", "/v2/devices/search", params=params)

    def get_device_alerts(self, device_id: int) -> List[Dict]:
        """
        Get alerts for a specific device.

        Args:
            device_id (int): Device identifier

        Returns:
            List of alert objects
        """
        return self._request("GET", f"/v2/devices/{device_id}/alerts")

    def get_device_activities(
        self,
        device_id: int,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        activity_type: Optional[str] = None,
        page_size: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> Dict:
        """
        Get activities for a specific device.

        Args:
            device_id (int): Device identifier
            start_time (float, optional): Start time in epoch seconds
            end_time (float, optional): End time in epoch seconds
            activity_type (str, optional): Filter by activity type
            page_size (int, optional): Number of results per page
            cursor (str, optional): Cursor for pagination

        Returns:
            Activities and pagination metadata
        """
        params = {}
        if start_time:
            params["from"] = start_time
        if end_time:
            params["to"] = end_time
        if activity_type:
            params["type"] = activity_type
        if page_size:
            params["pageSize"] = page_size
        if cursor:
            params["cursor"] = cursor

        return self._request(
            "GET", f"/v2/devices/{device_id}/activities", params=params
        )

    def get_device_processes(self, device_id: int) -> List[Dict]:
        """
        Get running processes for a specific device.

        Args:
            device_id (int): Device identifier

        Returns:
            List of process objects
        """
        return self._request("GET", f"/v2/devices/{device_id}/processes")

    def get_device_services(self, device_id: int) -> List[Dict]:
        """
        Get services for a specific device.

        Args:
            device_id (int): Device identifier

        Returns:
            List of service objects
        """
        return self._request("GET", f"/v2/devices/{device_id}/services")

    def get_device_software(self, device_id: int) -> List[Dict]:
        """
        Get installed software for a specific device.

        Args:
            device_id (int): Device identifier

        Returns:
            List of software objects
        """
        return self._request("GET", f"/v2/devices/{device_id}/software")

    def get_device_volumes(self, device_id: int) -> List[Dict]:
        """
        Get disk volumes for a specific device.

        Args:
            device_id (int): Device identifier

        Returns:
            List of volume objects
        """
        return self._request("GET", f"/v2/devices/{device_id}/volumes")

    def enable_maintenance_mode(self, device_id: int, duration: int) -> Dict:
        """
        Enable maintenance mode for a device.

        Args:
            device_id (int): Device identifier
            duration (int): Duration in seconds

        Returns:
            Updated device maintenance status
        """
        return self._request(
            "POST", f"/v2/devices/{device_id}/maintenance", json={"duration": duration}
        )

    def disable_maintenance_mode(self, device_id: int) -> None:
        """
        Disable maintenance mode for a device.

        Args:
            device_id (int): Device identifier
        """
        self._request("DELETE", f"/v2/devices/{device_id}/maintenance")

    def get_custom_fields_policy_conditions(self, policy_id: int) -> List[Dict]:
        """
        Get all custom fields policy conditions for specified policy.

        Args:
            policy_id (int): Policy identifier

        Returns:
            List of custom fields policy conditions
        """
        return self._request("GET", f"/v2/policies/{policy_id}/condition/custom-fields")

    def create_custom_fields_policy_condition(
        self,
        policy_id: int,
        display_name: str,
        match_all: Optional[List[Dict]] = None,
        match_any: Optional[List[Dict]] = None,
        **kwargs,
    ) -> Dict:
        """
        Creates custom fields policy condition for specified policy.

        Args:
            policy_id (int): Policy identifier
            display_name (str): Policy condition display name
            match_all (List[Dict], optional): Custom field conditions that must all match
            match_any (List[Dict], optional): Custom field conditions where any can match
            **kwargs: Additional condition properties (enabled, severity, priority, etc.)

        Returns:
            Created policy condition
        """
        data = {"displayName": display_name, **kwargs}
        if match_all:
            data["matchAll"] = match_all
        if match_any:
            data["matchAny"] = match_any

        return self._request(
            "POST", f"/v2/policies/{policy_id}/condition/custom-fields", json=data
        )

    def get_custom_fields_policy_condition(
        self, policy_id: int, condition_id: str
    ) -> Dict:
        """
        Get specified custom fields condition for specified policy.

        Args:
            policy_id (int): Policy identifier
            condition_id (str): Condition identifier

        Returns:
            Policy condition details
        """
        return self._request(
            "GET", f"/v2/policies/{policy_id}/condition/custom-fields/{condition_id}"
        )

    def get_windows_event_conditions(self, policy_id: int) -> List[Dict]:
        """
        Get all windows event conditions for specified policy.

        Args:
            policy_id (int): Policy identifier

        Returns:
            List of windows event conditions
        """
        return self._request("GET", f"/v2/policies/{policy_id}/condition/windows-event")

    def create_windows_event_condition(
        self,
        policy_id: int,
        source: str,
        event_ids: List[int],
        display_name: str,
        **kwargs,
    ) -> Dict:
        """
        Creates windows event condition for specified policy.

        Args:
            policy_id (int): Policy identifier
            source (str): Event Source
            event_ids (List[int]): List of Event IDs to monitor
            display_name (str): Policy condition display name
            **kwargs: Additional condition properties (enabled, severity, priority, etc.)

        Returns:
            Created windows event condition
        """
        data = {
            "source": source,
            "eventIds": event_ids,
            "displayName": display_name,
            **kwargs,
        }
        return self._request(
            "POST", f"/v2/policies/{policy_id}/condition/windows-event", json=data
        )

    def get_windows_event_condition(self, policy_id: int, condition_id: str) -> Dict:
        """
        Get specified windows event condition for specified policy.

        Args:
            policy_id (int): Policy identifier
            condition_id (str): Condition identifier

        Returns:
            Windows event condition details
        """
        return self._request(
            "GET", f"/v2/policies/{policy_id}/condition/windows-event/{condition_id}"
        )

    def delete_policy_condition(self, policy_id: int, condition_id: str) -> None:
        """
        Deletes specified policy condition from specified agent policy.

        Args:
            policy_id (int): Policy identifier
            condition_id (str): Condition identifier
        """
        self._request("DELETE", f"/v2/policies/{policy_id}/condition/{condition_id}")

    def configure_webhook(
        self,
        url: str,
        activities: Dict[str, List[str]],
        expand: Optional[List[str]] = None,
        headers: Optional[List[Dict[str, str]]] = None,
    ) -> None:
        """
        Creates or updates Webhook configuration for current application/client.

        Args:
            url (str): Callback (WebHook) URL for activity notifications
            activities (Dict[str, List[str]]): Activity filter mapping
            expand (List[str], optional): References to expand in payloads
            headers (List[Dict[str, str]], optional): Custom HTTP Headers
        """
        data = {"url": url, "activities": activities}
        if expand:
            data["expand"] = expand
        if headers:
            data["headers"] = headers

        self._request("PUT", "/v2/webhook", json=data)

    def disable_webhook(self) -> None:
        """
        Disables Webhook configuration for current application/client.
        """
        self._request("DELETE", "/v2/webhook")

    def list_policies(self) -> List[Dict]:
        """
        List all policies.

        Returns:
            List of policy objects
        """
        return self._request("GET", "/v2/policies")

    def list_active_jobs(self) -> List[Dict]:
        """
        List all active jobs.

        Returns:
            List of active job objects
        """
        return self._request("GET", "/v2/jobs")

    def list_activities(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        activity_type: Optional[str] = None,
        page_size: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> Dict:
        """
        List all activities.

        Args:
            start_time (float, optional): Start time in epoch seconds
            end_time (float, optional): End time in epoch seconds
            activity_type (str, optional): Filter by activity type
            page_size (int, optional): Number of results per page
            cursor (str, optional): Cursor for pagination

        Returns:
            Activities and pagination metadata
        """
        params = {}
        if start_time:
            params["from"] = start_time
        if end_time:
            params["to"] = end_time
        if activity_type:
            params["type"] = activity_type
        if page_size:
            params["pageSize"] = page_size
        if cursor:
            params["cursor"] = cursor

        return self._request("GET", "/v2/activities", params=params)

    def list_active_alerts(self) -> List[Dict]:
        """
        List all active alerts (triggered conditions).

        Returns:
            List of active alert objects
        """
        return self._request("GET", "/v2/alerts")

    def list_automation_scripts(self) -> List[Dict]:
        """
        List all available automation scripts.

        Returns:
            List of automation script objects
        """
        return self._request("GET", "/v2/automation/scripts")

    def list_device_custom_fields(self) -> List[Dict]:
        """
        Get all device custom fields.

        Returns:
            List of custom field objects
        """
        return self._request("GET", "/v2/device-custom-fields")

    def list_devices_detailed(
        self, page_size: Optional[int] = None, after: Optional[int] = None
    ) -> List[Dict]:
        """
        List devices with detailed information.

        Args:
            page_size (int, optional): Limit number of devices to return
            after (int, optional): Last Device Identifier from previous page

        Returns:
            List of detailed device objects
        """
        params = {}
        if page_size:
            params["pageSize"] = page_size
        if after:
            params["after"] = after

        return self._request("GET", "/v2/devices-detailed", params=params)

    def list_enabled_notification_channels(self) -> List[Dict]:
        """
        List all enabled notification channels.

        Returns:
            List of enabled notification channel objects
        """
        return self._request("GET", "/v2/notification-channels/enabled")

    def list_groups(self) -> List[Dict]:
        """
        List all groups (saved searches).

        Returns:
            List of group objects
        """
        return self._request("GET", "/v2/groups")

    def list_locations(self) -> List[Dict]:
        """
        List all locations.

        Returns:
            List of location objects
        """
        return self._request("GET", "/v2/locations")

    def list_device_roles(self) -> List[Dict]:
        """
        List all device roles.

        Returns:
            List of device role objects
        """
        return self._request("GET", "/v2/roles")

    def list_notification_channels(self) -> List[Dict]:
        """
        List all notification channels.

        Returns:
            List of notification channel objects
        """
        return self._request("GET", "/v2/notification-channels")

    def list_organizations_detailed(
        self, page_size: Optional[int] = None, after: Optional[int] = None
    ) -> List[Dict]:
        """
        List organizations with detailed information.

        Args:
            page_size (int, optional): Limit number of organizations to return
            after (int, optional): Last Organization Identifier from previous page

        Returns:
            List of detailed organization objects
        """
        params = {}
        if page_size:
            params["pageSize"] = page_size
        if after:
            params["after"] = after

        return self._request("GET", "/v2/organizations-detailed", params=params)

    def list_scheduled_tasks(self) -> List[Dict]:
        """
        List all scheduled tasks.

        Returns:
            List of scheduled task objects
        """
        return self._request("GET", "/v2/tasks")

    def list_software_products(self) -> List[Dict]:
        """
        List all supported 3rd party software.

        Returns:
            List of software product objects
        """
        return self._request("GET", "/v2/software-products")

    def list_users(self) -> List[Dict]:
        """
        List all users.

        Returns:
            List of user objects
        """
        return self._request("GET", "/v2/users")

    def get_organization_end_users(self, org_id: int) -> List[Dict]:
        """
        Get list of end users for an organization.

        Args:
            org_id (int): Organization identifier

        Returns:
            List of end user objects
        """
        return self._request("GET", f"/v2/organization/{org_id}/end-users")

    def get_organization_location_backup_usage(
        self, org_id: int, location_id: int
    ) -> Dict:
        """
        Get backup usage for a specific organization location.

        Args:
            org_id (int): Organization identifier
            location_id (int): Location identifier

        Returns:
            Backup usage information
        """
        return self._request(
            "GET", f"/v2/organization/{org_id}/locations/{location_id}/backup/usage"
        )

    def get_organization_custom_fields(self, org_id: int) -> List[Dict]:
        """
        Get custom fields for an organization.

        Args:
            org_id (int): Organization identifier

        Returns:
            List of custom field objects
        """
        return self._request("GET", f"/v2/organization/{org_id}/custom-fields")

    def update_organization_custom_fields(
        self, org_id: int, custom_fields: Dict
    ) -> Dict:
        """
        Update custom field values for an organization.

        Args:
            org_id (int): Organization identifier
            custom_fields (Dict): Custom field values to update

        Returns:
            Updated custom fields
        """
        return self._request(
            "PATCH", f"/v2/organization/{org_id}/custom-fields", json=custom_fields
        )

    def get_organization_devices(self, org_id: int) -> List[Dict]:
        """
        Get all devices for an organization.

        Args:
            org_id (int): Organization identifier

        Returns:
            List of device objects
        """
        return self._request("GET", f"/v2/organization/{org_id}/devices")

    def get_organization_locations_backup_usage(self, org_id: int) -> Dict:
        """
        Get backup usage for all locations in an organization.

        Args:
            org_id (int): Organization identifier

        Returns:
            Backup usage information for all locations
        """
        return self._request("GET", f"/v2/organization/{org_id}/locations/backup/usage")

    def get_device_jobs(self, device_id: int) -> List[Dict]:
        """
        Get currently running (active) jobs for a device.

        Args:
            device_id (int): Device identifier

        Returns:
            List of active job objects
        """
        return self._request("GET", f"/v2/device/{device_id}/jobs")

    def get_device_disks(self, device_id: int) -> List[Dict]:
        """
        Get disk drives for a device.

        Args:
            device_id (int): Device identifier

        Returns:
            List of disk drive objects
        """
        return self._request("GET", f"/v2/device/{device_id}/disks")

    def get_device_os_patch_installs(self, device_id: int) -> List[Dict]:
        """
        Get OS Patch installation report for device.

        Args:
            device_id (int): Device identifier

        Returns:
            List of OS patch installation reports
        """
        return self._request("GET", f"/v2/device/{device_id}/os-patch-installs")

    def get_device_software_patch_installs(self, device_id: int) -> List[Dict]:
        """
        Get Software Patch history for device.

        Args:
            device_id (int): Device identifier

        Returns:
            List of software patch installation history
        """
        return self._request("GET", f"/v2/device/{device_id}/software-patch-installs")

    def get_device_last_logged_on_user(self, device_id: int) -> Dict:
        """
        Get last logged-on user information for device.

        Args:
            device_id (int): Device identifier

        Returns:
            Last logged-on user information
        """
        return self._request("GET", f"/v2/device/{device_id}/last-logged-on-user")

    def get_device_network_interfaces(self, device_id: int) -> List[Dict]:
        """
        Get network interfaces for device.

        Args:
            device_id (int): Device identifier

        Returns:
            List of network interface objects
        """
        return self._request("GET", f"/v2/device/{device_id}/network-interfaces")

    def get_device_os_patches(self, device_id: int) -> List[Dict]:
        """
        Get OS Patches for device.

        Args:
            device_id (int): Device identifier

        Returns:
            List of OS patch objects
        """
        return self._request("GET", f"/v2/device/{device_id}/os-patches")

    def get_device_software_patches(self, device_id: int) -> List[Dict]:
        """
        Get Pending, Failed and Rejected Software patches for device.

        Args:
            device_id (int): Device identifier

        Returns:
            List of software patch objects
        """
        return self._request("GET", f"/v2/device/{device_id}/software-patches")

    def get_device_processors(self, device_id: int) -> List[Dict]:
        """
        Get processors for device.

        Args:
            device_id (int): Device identifier

        Returns:
            List of processor objects
        """
        return self._request("GET", f"/v2/device/{device_id}/processors")

    def get_device_windows_services(self, device_id: int) -> List[Dict]:
        """
        Get Windows services for device.

        Args:
            device_id (int): Device identifier

        Returns:
            List of Windows service objects
        """
        return self._request("GET", f"/v2/device/{device_id}/windows-services")

    def get_device_custom_fields(self, device_id: int) -> Dict:
        """
        Get custom fields for device.

        Args:
            device_id (int): Device identifier

        Returns:
            Device custom fields
        """
        return self._request("GET", f"/v2/device/{device_id}/custom-fields")

    def update_device_custom_fields(self, device_id: int, custom_fields: Dict) -> Dict:
        """
        Update custom field values for device.

        Args:
            device_id (int): Device identifier
            custom_fields (Dict): Custom field values to update

        Returns:
            Updated device custom fields
        """
        return self._request(
            "PATCH", f"/v2/device/{device_id}/custom-fields", json=custom_fields
        )

    def get_device_policy_overrides(self, device_id: int) -> Dict:
        """
        Get summary of device policy overrides.

        Args:
            device_id (int): Device identifier

        Returns:
            Device policy override summary
        """
        return self._request("GET", f"/v2/device/{device_id}/policy/overrides")

    def control_windows_service(
        self,
        device_id: int,
        service_id: str,
        action: Literal["START", "STOP", "RESTART", "PAUSE", "RESUME"],
    ) -> None:
        """Control a Windows service on a device."""
        if action not in ("START", "STOP", "RESTART", "PAUSE", "RESUME"):
            raise NinjaRMMValidationError("Invalid service control action", "action")

    def get_device_dashboard_url(self, device_id: int) -> str:
        """
        Get dashboard URL for a device.

        Args:
            device_id (int): Device identifier

        Returns:
            Dashboard URL string
        """
        return self._request("GET", f"/v2/device/{device_id}/dashboard-url")

    def reset_device_policy_overrides(self, device_id: int) -> None:
        """
        Reset all policy overrides for a device.

        Args:
            device_id (int): Device identifier
        """
        self._request("DELETE", f"/v2/device/{device_id}/policy/overrides")

    def reboot_device(self, device_id: int, mode: Literal["FORCE", "GRACEFUL"]) -> None:
        """
        Reboot a device.

        Args:
            device_id: Device identifier
            mode: Reboot mode, must be one of:
                - "FORCE": Force immediate reboot
                - "GRACEFUL": Allow graceful shutdown

        Raises:
            NinjaRMMValidationError: If mode is not "FORCE" or "GRACEFUL"
        """
        if mode not in ("FORCE", "GRACEFUL"):
            raise NinjaRMMValidationError(
                "Invalid reboot mode. Must be 'FORCE' or 'GRACEFUL'", "mode"
            )
        self._request("POST", f"/v2/device/{device_id}/reboot/{mode}")

    def remove_device_owner(self, device_id: int) -> None:
        """
        Remove owner from a device.

        Args:
            device_id (int): Device identifier
        """
        self._request("DELETE", f"/v2/device/{device_id}/owner")

    def get_device_scripting_options(self, device_id: int) -> Dict:
        """
        Get scripting options for a device.

        Args:
            device_id (int): Device identifier

        Returns:
            Device scripting options
        """
        return self._request("GET", f"/v2/device/{device_id}/scripting/options")

    def run_device_script(self, device_id: int, script_id: int, **kwargs) -> Dict:
        """
        Run a script or built-in action on a device.

        Args:
            device_id (int): Device identifier
            script_id (int): Script identifier
            **kwargs: Additional script parameters

        Returns:
            Script execution result
        """
        data = {"scriptId": script_id, **kwargs}
        return self._request("POST", f"/v2/device/{device_id}/script/run", json=data)

    def set_device_owner(self, device_id: int, owner_uid: str) -> None:
        """
        Set owner for a device.

        Args:
            device_id (int): Device identifier
            owner_uid (str): Owner user ID
        """
        self._request("POST", f"/v2/device/{device_id}/owner/{owner_uid}")

    def configure_windows_service(
        self, device_id: int, service_id: str, config: Dict
    ) -> None:
        """
        Modify Windows Service configuration.

        Args:
            device_id (int): Device identifier
            service_id (str): Service identifier
            config (Dict): Service configuration
        """
        self._request(
            "POST",
            f"/v2/device/{device_id}/windows-service/{service_id}/configure",
            json=config,
        )

    def generate_organization_installer(self, **kwargs) -> Dict:
        """
        Generate installer for organization.

        Args:
            **kwargs: Installer generation parameters

        Returns:
            Installer information
        """
        return self._request("POST", "/v2/organization/generate-installer", json=kwargs)

    def generate_location_installer(
        self, org_id: int, location_id: int, installer_type: str
    ) -> Dict:
        """
        Generate installer for specific location.

        Args:
            org_id (int): Organization identifier
            location_id (int): Location identifier
            installer_type (str): Type of installer

        Returns:
            Installer information
        """
        return self._request(
            "GET",
            f"/v2/organization/{org_id}/location/{location_id}/installer/{installer_type}",
        )

    def create_policy(self, name: str, **kwargs) -> Dict:
        """
        Create a new policy.

        Args:
            name (str): Policy name
            **kwargs: Additional policy properties

        Returns:
            Created policy object
        """
        data = {"name": name, **kwargs}
        return self._request("POST", "/v2/policies", json=data)

    def get_location_custom_fields(self, org_id: int, location_id: int) -> Dict:
        """
        Get custom fields for a specific location.

        Args:
            org_id (int): Organization identifier
            location_id (int): Location identifier

        Returns:
            Location custom fields
        """
        return self._request(
            "GET", f"/v2/organization/{org_id}/location/{location_id}/custom-fields"
        )

    def update_location_custom_fields(
        self, org_id: int, location_id: int, custom_fields: Dict
    ) -> Dict:
        """
        Update custom field values for a specific location.

        Args:
            org_id (int): Organization identifier
            location_id (int): Location identifier
            custom_fields (Dict): Custom field values to update

        Returns:
            Updated location custom fields
        """
        return self._request(
            "PATCH",
            f"/v2/organization/{org_id}/location/{location_id}/custom-fields",
            json=custom_fields,
        )

    def create_location_edf_document(self, json_data, org_id):
        """
        Create a location EDF document from MongoDB JSON data.

        Args:
            json_data (List[Dict]): Location EDF data from MongoDB
            org_id (int): Organization identifier

        Returns:
            Dict: Document formatted for the NinjaRMM API with fields:
                - documentName: "Onboarding-Locations"
                - documentDescription: "Onboarding-Locations"
                - fields: Mapped fields from EDF data
                - documentTemplateId: 23
                - organizationId: org_id
                - locationName: Location name
        """
        # Get the first record to extract common location info
        first_record = json_data[0]

        # Initialize fields dictionary with required field structure
        fields = {
            "organization": org_id,
            # Location name from the first record
            "location": first_record["Name"],
            "locations": [first_record["Name"]],  # Array of location names
            "remoteSupportOnly": False,  # Default value
        }

        # Process security-specific fields
        for entry in json_data:
            if entry["Title"] == "DNS Filter":
                # Convert 'Enabled'/'Disabled' to boolean
                fields["deployDnsfilter"] = entry["DropdownValue"] == "Enabled"

            elif entry["Title"] == "DNS Filter Software Key":
                fields["dnsfilterlocationkey"] = entry["TextFieldValue"] or None

            elif entry["Title"] == "DefensX":
                # Convert 'Enabled'/'Disabled' to boolean
                fields["deployDefensx"] = entry["DropdownValue"] == "Enabled"

            elif entry["Title"] == "DefensX Software Key":
                fields["defensxlocationkey"] = entry["TextFieldValue"] or None

            # Map Remote Support fields
            elif (
                entry["Title"] == "Remote Servers"
                or entry["Title"] == "Remote Workstations"
            ):
                if entry["CheckboxValue"] is True:
                    fields["remoteSupportOnly"] = True

        # Create the final document structure
        document = {
            "documentName": "Onboarding-Locations",
            "documentDescription": "Onboarding-Locations",
            "fields": fields,
            "documentTemplateId": 23,
            "organizationId": org_id,
            "locationName": first_record["Name"],
        }

        return document

    def __enter__(self) -> "NinjaRMMClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self) -> None:
        """Close the session and cleanup resources."""
        self.session.close()

    def set_timestamp_conversion(self, enabled: bool) -> None:
        """
        Enable or disable automatic timestamp conversion.

        Args:
            enabled: Whether to convert epoch timestamps to ISO format
        """
        self.convert_timestamps = enabled
        logger.info(f"Timestamp conversion {'enabled' if enabled else 'disabled'}")

    def get_timestamp_conversion_status(self) -> bool:
        """
        Get the current timestamp conversion status.

        Returns:
            True if timestamp conversion is enabled, False otherwise
        """
        return self.convert_timestamps

    # Auto-pagination methods for easy retrieval of all records

    def get_all_organizations(
        self, page_size: int = 100, org_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Get ALL organizations using automatic pagination.

        Args:
            page_size: Number of items per page (default: 100)
            org_filter: Organization filter

        Returns:
            List[Dict]: All organizations from all pages
        """
        return self._get_all_with_after(
            self.get_organizations, page_size=page_size, org_filter=org_filter
        )

    def get_all_organizations_detailed(
        self, page_size: int = 100, org_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Get ALL organizations with detailed information using automatic pagination.

        Args:
            page_size: Number of items per page (default: 100)
            org_filter: Organization filter

        Returns:
            List[Dict]: All detailed organizations from all pages
        """
        return self._get_all_with_after(
            self.get_organizations_detailed, page_size=page_size, org_filter=org_filter
        )

    def get_all_devices(
        self,
        page_size: int = 100,
        org_filter: Optional[str] = None,
        expand: Optional[str] = None,
        include_backup_usage: bool = False,
    ) -> List[Dict]:
        """
        Get ALL devices using automatic pagination.

        Args:
            page_size: Number of items per page (default: 100)
            org_filter: Organization filter
            expand: Expand fields
            include_backup_usage: Whether to include backup usage data

        Returns:
            List[Dict]: All devices from all pages
        """
        return self._get_all_with_after(
            self.get_devices,
            page_size=page_size,
            org_filter=org_filter,
            expand=expand,
            include_backup_usage=include_backup_usage,
        )

    def get_all_devices_detailed(
        self,
        page_size: int = 100,
        org_filter: Optional[str] = None,
        expand: Optional[str] = None,
        include_backup_usage: bool = False,
    ) -> List[Dict]:
        """
        Get ALL devices with detailed information using automatic pagination.

        Args:
            page_size: Number of items per page (default: 100)
            org_filter: Organization filter
            expand: Expand fields
            include_backup_usage: Whether to include backup usage data

        Returns:
            List[Dict]: All detailed devices from all pages
        """
        return self._get_all_with_after(
            self.get_devices_detailed,
            page_size=page_size,
            org_filter=org_filter,
            expand=expand,
            include_backup_usage=include_backup_usage,
        )

    def search_all_devices(
        self, query: str, page_size: int = 100, **kwargs
    ) -> List[Dict]:
        """
        Search ALL devices using automatic cursor-based pagination.

        Args:
            query: Search query
            page_size: Number of items per page (default: 100)
            **kwargs: Additional search parameters

        Returns:
            List[Dict]: All matching devices from all pages
        """
        return self._get_all_with_cursor(
            self.search_devices, page_size=page_size, query=query, **kwargs
        )

    def get_all_device_activities(
        self,
        device_id: int,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        activity_type: Optional[str] = None,
        page_size: int = 100,
    ) -> List[Dict]:
        """
        Get ALL device activities using automatic cursor-based pagination.

        Args:
            device_id: Device ID
            start_time: Start time (Unix timestamp)
            end_time: End time (Unix timestamp)
            activity_type: Activity type filter
            page_size: Number of items per page (default: 100)

        Returns:
            List[Dict]: All device activities from all pages
        """
        return self._get_all_with_cursor(
            self.get_device_activities,
            page_size=page_size,
            device_id=device_id,
            start_time=start_time,
            end_time=end_time,
            activity_type=activity_type,
        )

    def get_all_activities(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        activity_type: Optional[str] = None,
        page_size: int = 100,
    ) -> List[Dict]:
        """
        Get ALL activities using automatic cursor-based pagination.

        Args:
            start_time: Start time (Unix timestamp)
            end_time: End time (Unix timestamp)
            activity_type: Activity type filter
            page_size: Number of items per page (default: 100)

        Returns:
            List[Dict]: All activities from all pages
        """
        return self._get_all_with_cursor(
            self.list_activities,
            page_size=page_size,
            start_time=start_time,
            end_time=end_time,
            activity_type=activity_type,
        )

    # Iterator methods for memory-efficient processing

    def iter_all_organizations(
        self, page_size: int = 100, org_filter: Optional[str] = None
    ) -> Iterator[Dict]:
        """
        Iterate through ALL organizations one at a time using automatic pagination.
        Memory-efficient for processing large datasets.

        Args:
            page_size: Number of items per page (default: 100)
            org_filter: Organization filter

        Yields:
            Dict: Organization objects one at a time
        """
        yield from self._paginate_with_after(
            self.get_organizations, page_size=page_size, org_filter=org_filter
        )

    def iter_all_devices(
        self,
        page_size: int = 100,
        org_filter: Optional[str] = None,
        expand: Optional[str] = None,
        include_backup_usage: bool = False,
    ) -> Iterator[Dict]:
        """
        Iterate through ALL devices one at a time using automatic pagination.
        Memory-efficient for processing large datasets.

        Args:
            page_size: Number of items per page (default: 100)
            org_filter: Organization filter
            expand: Expand fields
            include_backup_usage: Whether to include backup usage data

        Yields:
            Dict: Device objects one at a time
        """
        yield from self._paginate_with_after(
            self.get_devices,
            page_size=page_size,
            org_filter=org_filter,
            expand=expand,
            include_backup_usage=include_backup_usage,
        )

    def iter_search_devices(
        self, query: str, page_size: int = 100, **kwargs
    ) -> Iterator[Dict]:
        """
        Iterate through ALL search results one at a time using automatic cursor-based pagination.
        Memory-efficient for processing large datasets.

        Args:
            query: Search query
            page_size: Number of items per page (default: 100)
            **kwargs: Additional search parameters

        Yields:
            Dict: Device objects one at a time
        """
        yield from self._paginate_with_cursor(
            self.search_devices, page_size=page_size, query=query, **kwargs
        )

    # Auto-pagination methods for query endpoints (/v2/queries)

    def query_all_windows_services(
        self,
        device_filter: Optional[str] = None,
        name: Optional[str] = None,
        state: Optional[str] = None,
        page_size: int = 100,
    ) -> List[Dict]:
        """
        Query ALL Windows services using automatic cursor-based pagination.

        Args:
            device_filter: Device filter expression
            name: Service name filter
            state: Service state filter
            page_size: Number of items per page (default: 100)

        Returns:
            List[Dict]: All Windows services from all pages
        """
        return self._get_all_with_cursor(
            self.query_windows_services,
            page_size=page_size,
            device_filter=device_filter,
            name=name,
            state=state,
        )

    def query_all_operating_systems(
        self,
        device_filter: Optional[str] = None,
        timestamp_filter: Optional[str] = None,
        page_size: int = 100,
    ) -> List[Dict]:
        """
        Query ALL operating systems using automatic cursor-based pagination.

        Args:
            device_filter: Device filter expression
            timestamp_filter: Timestamp filter expression
            page_size: Number of items per page (default: 100)

        Returns:
            List[Dict]: All operating systems from all pages
        """
        return self._get_all_with_cursor(
            self.query_operating_systems,
            page_size=page_size,
            device_filter=device_filter,
            timestamp_filter=timestamp_filter,
        )

    def query_all_os_patches(
        self,
        device_filter: Optional[str] = None,
        timestamp_filter: Optional[str] = None,
        status: Optional[str] = None,
        patch_type: Optional[str] = None,
        severity: Optional[str] = None,
        page_size: int = 100,
    ) -> List[Dict]:
        """
        Query ALL OS patches using automatic cursor-based pagination.

        Args:
            device_filter: Device filter expression
            timestamp_filter: Timestamp filter expression
            status: Patch status filter
            patch_type: Patch type filter
            severity: Patch severity filter
            page_size: Number of items per page (default: 100)

        Returns:
            List[Dict]: All OS patches from all pages
        """
        return self._get_all_with_cursor(
            self.query_os_patches,
            page_size=page_size,
            device_filter=device_filter,
            timestamp_filter=timestamp_filter,
            status=status,
            patch_type=patch_type,
            severity=severity,
        )

    def query_all_custom_fields(
        self,
        device_filter: Optional[str] = None,
        updated_after: Optional[str] = None,
        fields: Optional[str] = None,
        show_secure_values: Optional[bool] = None,
        page_size: int = 100,
    ) -> List[Dict]:
        """
        Query ALL custom fields using automatic cursor-based pagination.

        Args:
            device_filter: Device filter expression
            updated_after: Include only fields updated after this timestamp
            fields: Comma-separated list of field names to include
            show_secure_values: Whether to show secure field values
            page_size: Number of items per page (default: 100)

        Returns:
            List[Dict]: All custom fields from all pages
        """
        return self._get_all_with_cursor(
            self.query_custom_fields,
            page_size=page_size,
            device_filter=device_filter,
            updated_after=updated_after,
            fields=fields,
            show_secure_values=show_secure_values,
        )

    def query_all_software(
        self,
        device_filter: Optional[str] = None,
        installed_before: Optional[str] = None,
        installed_after: Optional[str] = None,
        page_size: int = 100,
    ) -> List[Dict]:
        """
        Query ALL software using automatic cursor-based pagination.

        Args:
            device_filter: Device filter expression
            installed_before: Include software installed before this date
            installed_after: Include software installed after this date
            page_size: Number of items per page (default: 100)

        Returns:
            List[Dict]: All software from all pages
        """
        return self._get_all_with_cursor(
            self.query_software,
            page_size=page_size,
            device_filter=device_filter,
            installed_before=installed_before,
            installed_after=installed_after,
        )

    def query_all_backup_usage(
        self, include_deleted_devices: Optional[bool] = None, page_size: int = 100
    ) -> List[Dict]:
        """
        Query ALL backup usage using automatic cursor-based pagination.

        Args:
            include_deleted_devices: Whether to include deleted devices
            page_size: Number of items per page (default: 100)

        Returns:
            List[Dict]: All backup usage data from all pages
        """
        return self._get_all_with_cursor(
            self.query_backup_usage,
            page_size=page_size,
            include_deleted_devices=include_deleted_devices,
        )

    # Iterator versions for query endpoints (memory-efficient)

    def iter_query_windows_services(
        self,
        device_filter: Optional[str] = None,
        name: Optional[str] = None,
        state: Optional[str] = None,
        page_size: int = 100,
    ) -> Iterator[Dict]:
        """
        Iterate through ALL Windows services one at a time using automatic cursor-based pagination.
        Memory-efficient for processing large datasets.
        """
        yield from self._paginate_with_cursor(
            self.query_windows_services,
            page_size=page_size,
            device_filter=device_filter,
            name=name,
            state=state,
        )

    def iter_query_custom_fields(
        self,
        device_filter: Optional[str] = None,
        updated_after: Optional[str] = None,
        fields: Optional[str] = None,
        show_secure_values: Optional[bool] = None,
        page_size: int = 100,
    ) -> Iterator[Dict]:
        """
        Iterate through ALL custom fields one at a time using automatic cursor-based pagination.
        Memory-efficient for processing large datasets.
        """
        yield from self._paginate_with_cursor(
            self.query_custom_fields,
            page_size=page_size,
            device_filter=device_filter,
            updated_after=updated_after,
            fields=fields,
            show_secure_values=show_secure_values,
        )

    def iter_organizations(self, page_size: int = 100) -> Iterator[Dict]:
        """
        Iterate through all organizations using pagination.

        Args:
            page_size: Number of items per page

        Yields:
            Organization objects one at a time
        """
        last_id = None
        while True:
            page = self.get_organizations(page_size=page_size, after=last_id)
            if not page:
                break
            yield from page
            last_id = page[-1]["id"]

    def create_location(
        self,
        org_id: int,
        name: str,
        description: Optional[str] = None,
        address: Optional[str] = None,
    ) -> dict:
        """Create a new location for an organization

        Args:
            org_id (int): Organization ID
            name (str): Location name
            description (str, optional): Location description. Defaults to None.
            address (str, optional): Location address. Defaults to None.

        Returns:
            dict: Created location object
        """
        url = f"{self.base_url}/v2/organization/{org_id}/locations"
        data = {"name": name, "description": description, "address": address}

        # Remove None values
        data = {k: v for k, v in data.items() if v is not None}

        response = self.session.post(url, json=data)
        response.raise_for_status()
        return response.json()

    def get_locations_by_organization_id(self, org_id: int) -> List[Dict]:
        """Get all locations for an organization

        Args:
            org_id (int): Organization ID

        Returns:
            List[Dict]: List of location objects
        """
        return self._request(
            "GET", f"/v2/organization/{org_id}/locations"
        )

    def get_locations(self) -> List[Dict]:
        """Get all locations for an organization


        Returns:
            List[Dict]: List of location objects
        """
        return self._request("GET", "/v2/locations")

    def update_location(
        self,
        org_id: int,
        location_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        address: Optional[str] = None,
    ) -> Dict:
        """Update an existing location for an organization

        Args:
            org_id (int): Organization ID
            location_id (int): Location ID to update
            name (str, optional): Location name. Defaults to None.
            description (str, optional): Location description. Defaults to None.
            address (str, optional): Location address. Defaults to None.

        Returns:
            Dict: Updated location object
        """
        url = f"{self.base_url}/v2/organization/{org_id}/locations/{location_id}"
        data = {"name": name, "description": description, "address": address}

        # Remove None values
        data = {k: v for k, v in data.items() if v is not None}

        response = self.session.patch(url, json=data)
        response.raise_for_status()
        return response.json()

    def create_organization_documents(self, documents: List[Dict]) -> List[Dict]:
        """
        Create multiple organization documents.

        Args:
            documents (List[Dict]): List of documents to create, each containing:
                - documentName (str): Document name
                - documentDescription (str, optional): Document description
                - fields (Dict, optional): Document fields as key-value pairs
                - documentTemplateId (int): Document template identifier
                - organizationId (int): Organization identifier

        Returns:
            List[Dict]: List of created organization documents containing:
                - documentId (int): Document identifier
                - documentName (str): Document name
                - documentDescription (str): Document description
                - documentUpdateTime (float): Document last updated
                - fields (List[Dict]): Updated fields
                - documentTemplateId (int): Document template identifier
                - documentTemplateName (str): Document template name
                - organizationId (int): Organization identifier
        """
        # Ensure documents is a list
        if isinstance(documents, dict):
            documents = [documents]
        elif not isinstance(documents, list):
            raise ValueError(
                "documents must be a list of dictionaries or a single dictionary"
            )

        # Process each document to remove None values from fields
        processed_documents = []
        for doc in documents:
            if not isinstance(doc, dict):
                raise ValueError("Each document must be a dictionary")

            processed_doc = doc.copy()
            if "fields" in processed_doc and isinstance(processed_doc["fields"], dict):
                # Remove None values from fields
                processed_doc["fields"] = {
                    k: v for k, v in processed_doc["fields"].items() if v is not None
                }
            processed_documents.append(processed_doc)

        return self._request(
            "POST", "/v2/organization/documents", json=processed_documents
        )

    def create_organization_document(
        self,
        organization_id: int,
        document_template_id: int,
        document_name: str,
        document_description: Optional[str] = None,
        fields: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """
        Create a single organization document.

        Args:
            organization_id (int): Organization identifier
            document_template_id (int): Document template identifier
            document_name (str): Document name
            document_description (str, optional): Document description
            fields (Dict[str, Any], optional): Document fields as key-value pairs

        Returns:
            Dict: Created organization document
        """
        document = {
            "documentName": document_name,
            "documentTemplateId": document_template_id,
            "organizationId": organization_id,
        }

        if document_description is not None:
            document["documentDescription"] = document_description
        if fields is not None:
            if not isinstance(fields, dict):
                raise ValueError("fields must be a dictionary")
            # Remove None values from fields
            document["fields"] = {k: v for k, v in fields.items() if v is not None}

        # Create a single document using the bulk endpoint
        return self.create_organization_documents([document])[0]

    def update_organization_documents(self, documents: List[Dict]) -> List[Dict]:
        """
        Update multiple organization documents.

        Args:
            documents (List[Dict]): List of documents to update, each containing:
                - documentId (int): Document identifier
                - documentName (str, optional): Document name
                - documentDescription (str, optional): Document description
                - fields (Dict, optional): Document fields as key-value pairs

        Returns:
            List[Dict]: List of updated organization documents
        """
        # Ensure documents is a list
        if isinstance(documents, dict):
            documents = [documents]
        elif not isinstance(documents, list):
            raise ValueError(
                "documents must be a list of dictionaries or a single dictionary"
            )

        # Process each document to remove None values from fields
        processed_documents = []
        for doc in documents:
            if not isinstance(doc, dict):
                raise ValueError("Each document must be a dictionary")

            processed_doc = doc.copy()
            if "fields" in processed_doc and isinstance(processed_doc["fields"], dict):
                # Remove None values from fields
                processed_doc["fields"] = {
                    k: v for k, v in processed_doc["fields"].items() if v is not None
                }
            processed_documents.append(processed_doc)

        return self._request(
            "PATCH", "/v2/organization/documents", json=processed_documents
        )

    def update_organization_document(
        self,
        document_id: int,
        document_name: Optional[str] = None,
        document_description: Optional[str] = None,
        fields: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """
        Update a single organization document.

        Args:
            document_id (int): Document identifier
            document_name (str, optional): Document name
            document_description (str, optional): Document description
            fields (Dict[str, Any], optional): Document fields as key-value pairs

        Returns:
            Dict: Updated organization document
        """
        document = {}

        if document_name is not None:
            document["documentName"] = document_name
        if document_description is not None:
            document["documentDescription"] = document_description
        if fields is not None:
            if not isinstance(fields, dict):
                raise ValueError("fields must be a dictionary")
            # Remove None values from fields
            document["fields"] = {k: v for k, v in fields.items() if v is not None}

        return self._request(
            "PATCH", f"/v2/organization/documents/{document_id}", json=document
        )

    def update_document_template(
        self,
        template_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        mandatory: Optional[bool] = None,
        fields: Optional[List[Dict]] = None,
        available_to_all_technicians: Optional[bool] = None,
        allowed_technician_roles: Optional[List[int]] = None,
    ) -> Dict:
        """
        Update a document template.

        Args:
            template_id (int): Template identifier
            name (str, optional): Template name
            description (str, optional): Template description
            mandatory (bool, optional): Whether document is mandatory
            fields (List[Dict], optional): Template fields configuration
            available_to_all_technicians (bool, optional): Whether template is available to all technicians
            allowed_technician_roles (List[int], optional): List of technician role IDs that can use this template

        Returns:
            Dict: Updated document template
        """
        data = {}

        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description
        if mandatory is not None:
            data["mandatory"] = mandatory
        if fields is not None:
            if not isinstance(fields, list):
                raise ValueError("fields must be a list of dictionaries")
            # Process each field to remove None values
            processed_fields = []
            for field in fields:
                if not isinstance(field, dict):
                    raise ValueError("Each field must be a dictionary")
                processed_field = {k: v for k, v in field.items() if v is not None}
                processed_fields.append(processed_field)
            data["fields"] = processed_fields
        if available_to_all_technicians is not None:
            data["availableToAllTechnicians"] = available_to_all_technicians
        if allowed_technician_roles is not None:
            if not isinstance(allowed_technician_roles, list):
                raise ValueError("allowed_technician_roles must be a list of integers")
            data["allowedTechnicianRoles"] = allowed_technician_roles

        return self._request("PUT", f"/v2/templates/{template_id}", json=data)

    def get_all_organization_documents(
        self,
        group_by: Optional[Literal["TEMPLATE", "ORGANIZATION"]] = None,
        organization_ids: Optional[str] = None,
        template_ids: Optional[str] = None,
        template_name: Optional[str] = None,
        document_name: Optional[str] = None,
    ) -> List[Dict]:
        """
        List all organization documents with field values.

        Args:
            group_by (Literal["TEMPLATE", "ORGANIZATION"], optional): Group results by template or organization
            organization_ids (str, optional): Filter by organization IDs (comma-separated)
            template_ids (str, optional): Filter by template IDs (comma-separated)
            template_name (str, optional): Filter by template name
            document_name (str, optional): Filter by document name

        Returns:
            List[Dict]: List of organization documents containing:
                - documentId (int): Document identifier
                - documentName (str): Document name
                - documentDescription (str): Document description
                - documentUpdateTime (float): Document last updated
                - fields (List[Dict]): List of fields with:
                    - name (str): Field name
                    - value (Any): Field value
                    - valueUpdateTime (float): Field value last updated
                - documentTemplateId (int): Document template identifier
                - documentTemplateName (str): Document template name
                - organizationId (int): Organization identifier
        """
        params = {}
        if group_by is not None:
            if group_by not in ("TEMPLATE", "ORGANIZATION"):
                raise ValueError("group_by must be either 'TEMPLATE' or 'ORGANIZATION'")
            params["groupBy"] = group_by
        if organization_ids is not None:
            params["organizationIds"] = organization_ids
        if template_ids is not None:
            params["templateIds"] = template_ids
        if template_name is not None:
            params["templateName"] = template_name
        if document_name is not None:
            params["documentName"] = document_name

        return self._request("GET", "/v2/organization/documents", params=params)

    def get_organization_documents(self, org_id: int) -> List[Dict]:
        """
        List organization documents with field values.

        Args:
            org_id (int): Organization identifier

        Returns:
            List[Dict]: List of organization documents containing:
                - documentId (int): Document identifier
                - documentName (str): Document name
                - documentDescription (str): Document description
                - documentUpdateTime (float): Document last updated
                - fields (List[Dict]): List of fields with:
                    - name (str): Field name
                    - value (Any): Field value
                    - valueUpdateTime (float): Field value last updated
                - documentTemplateId (int): Document template identifier
                - documentTemplateName (str): Document template name
                - organizationId (int): Organization identifier
        """
        return self._request("GET", f"/v2/organization/{org_id}/documents")

    def update_organization_document_by_id(
        self,
        org_id: int,
        document_id: int,
        document_name: Optional[str] = None,
        document_description: Optional[str] = None,
        fields: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """
        Update an organization document by ID and return the updated version.

        Args:
            org_id (int): Organization identifier
            document_id (int): Organization document identifier
            document_name (str, optional): Document name
            document_description (str, optional): Document description
            fields (Dict[str, Any], optional): Document fields as key-value pairs

        Returns:
            Dict: Updated organization document containing:
                - documentId (int): Document identifier
                - documentName (str): Document name
                - documentDescription (str): Document description
                - documentUpdateTime (float): Document last updated
                - updatedFields (List[Dict]): List of updated fields with:
                    - name (str): Field name
                    - value (Any): Field value
                    - valueUpdateTime (float): Field value last updated
                - documentTemplateId (int): Document template identifier
                - documentTemplateName (str): Document template name
                - organizationId (int): Organization identifier
        """
        data = {}
        if document_name is not None:
            data["documentName"] = document_name
        if document_description is not None:
            data["documentDescription"] = document_description
        if fields is not None:
            if not isinstance(fields, dict):
                raise ValueError("fields must be a dictionary")
            # Remove None values from fields
            data["fields"] = {k: v for k, v in fields.items() if v is not None}

        return self._request(
            "POST", f"/v2/organization/{org_id}/document/{document_id}", json=data
        )

    # Query endpoints for system information reports
    def query_windows_services(
        self,
        device_filter: Optional[str] = None,
        name: Optional[str] = None,
        state: Optional[str] = None,
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
    ) -> Dict:
        """
        Get Windows services report.

        Args:
            device_filter (str, optional): Device filter
            name (str, optional): Service name
            state (str, optional): Service state (UNKNOWN, STOPPED, START_PENDING, RUNNING,
                                   STOP_PENDING, PAUSE_PENDING, PAUSED, CONTINUE_PENDING)
            cursor (str, optional): Cursor name for pagination
            page_size (int, optional): Limit number of records per page (10-10000, default 1000)

        Returns:
            Dict: Windows services report with cursor and results
        """
        params = {}
        if device_filter:
            params["df"] = device_filter
        if name:
            params["name"] = name
        if state:
            params["state"] = state
        if cursor:
            params["cursor"] = cursor
        if page_size:
            params["pageSize"] = str(page_size)

        return self._request("GET", "/v2/queries/windows-services", params=params)

    def query_operating_systems(
        self,
        device_filter: Optional[str] = None,
        timestamp_filter: Optional[str] = None,
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
    ) -> Dict:
        """
        Get operating systems report.

        Args:
            device_filter (str, optional): Device filter
            timestamp_filter (str, optional): Monitoring timestamp filter
            cursor (str, optional): Cursor name for pagination
            page_size (int, optional): Limit number of records per page

        Returns:
            Dict: Operating systems report with cursor and results
        """
        params = {}
        if device_filter:
            params["df"] = device_filter
        if timestamp_filter:
            params["ts"] = timestamp_filter
        if cursor:
            params["cursor"] = cursor
        if page_size:
            params["pageSize"] = str(page_size)

        return self._request("GET", "/v2/queries/operating-systems", params=params)

    def query_os_patches(
        self,
        device_filter: Optional[str] = None,
        timestamp_filter: Optional[str] = None,
        status: Optional[str] = None,
        patch_type: Optional[str] = None,
        severity: Optional[str] = None,
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
    ) -> Dict:
        """
        Get pending, failed and rejected OS patches report.

        Args:
            device_filter (str, optional): Device filter
            timestamp_filter (str, optional): Monitoring timestamp filter
            status (str, optional): Patch status filter
            patch_type (str, optional): Patch type filter
            severity (str, optional): Patch severity filter
            cursor (str, optional): Cursor name for pagination
            page_size (int, optional): Limit number of records per page

        Returns:
            Dict: OS patches report with cursor and results
        """
        params = {}
        if device_filter:
            params["df"] = device_filter
        if timestamp_filter:
            params["ts"] = timestamp_filter
        if status:
            params["status"] = status
        if patch_type:
            params["type"] = patch_type
        if severity:
            params["severity"] = severity
        if cursor:
            params["cursor"] = cursor
        if page_size:
            params["pageSize"] = str(page_size)

        return self._request("GET", "/v2/queries/os-patches", params=params)

    def query_raid_controllers(
        self,
        device_filter: Optional[str] = None,
        timestamp_filter: Optional[str] = None,
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
    ) -> Dict:
        """
        Get RAID controllers report.

        Args:
            device_filter (str, optional): Device filter
            timestamp_filter (str, optional): Monitoring timestamp filter
            cursor (str, optional): Cursor name for pagination
            page_size (int, optional): Limit number of records per page

        Returns:
            Dict: RAID controllers report with cursor and results
        """
        params = {}
        if device_filter:
            params["df"] = device_filter
        if timestamp_filter:
            params["ts"] = timestamp_filter
        if cursor:
            params["cursor"] = cursor
        if page_size:
            params["pageSize"] = str(page_size)

        return self._request("GET", "/v2/queries/raid-controllers", params=params)

    def query_os_patch_installs(
        self,
        device_filter: Optional[str] = None,
        status: Optional[str] = None,
        installed_before: Optional[str] = None,
        installed_after: Optional[str] = None,
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
    ) -> Dict:
        """
        Get OS patch installation report.

        Args:
            device_filter (str, optional): Device filter
            status (str, optional): Patch status filter (FAILED, INSTALLED)
            installed_before (str, optional): Include patches installed before specified date
            installed_after (str, optional): Include patches installed after specified date
            cursor (str, optional): Cursor name for pagination
            page_size (int, optional): Limit number of records per page

        Returns:
            Dict: OS patch installs report with cursor and results
        """
        params = {}
        if device_filter:
            params["df"] = device_filter
        if status:
            params["status"] = status
        if installed_before:
            params["installedBefore"] = installed_before
        if installed_after:
            params["installedAfter"] = installed_after
        if cursor:
            params["cursor"] = cursor
        if page_size:
            params["pageSize"] = str(page_size)

        return self._request("GET", "/v2/queries/os-patch-installs", params=params)

    def query_computer_systems(
        self,
        device_filter: Optional[str] = None,
        timestamp_filter: Optional[str] = None,
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
    ) -> Dict:
        """
        Get computer systems report.

        Args:
            device_filter (str, optional): Device filter
            timestamp_filter (str, optional): Monitoring timestamp filter
            cursor (str, optional): Cursor name for pagination
            page_size (int, optional): Limit number of records per page

        Returns:
            Dict: Computer systems report with cursor and results
        """
        params = {}
        if device_filter:
            params["df"] = device_filter
        if timestamp_filter:
            params["ts"] = timestamp_filter
        if cursor:
            params["cursor"] = cursor
        if page_size:
            params["pageSize"] = str(page_size)

        return self._request("GET", "/v2/queries/computer-systems", params=params)

    def query_device_health(
        self,
        device_filter: Optional[str] = None,
        health: Optional[str] = None,
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
    ) -> Dict:
        """
        Get device health report.

        Args:
            device_filter (str, optional): Device filter
            health (str, optional): Health status filter
            cursor (str, optional): Cursor name for pagination
            page_size (int, optional): Limit number of records per page

        Returns:
            Dict: Device health report with cursor and results
        """
        params = {}
        if device_filter:
            params["df"] = device_filter
        if health:
            params["health"] = health
        if cursor:
            params["cursor"] = cursor
        if page_size:
            params["pageSize"] = str(page_size)

        return self._request("GET", "/v2/queries/device-health", params=params)

    def query_disks(
        self,
        device_filter: Optional[str] = None,
        timestamp_filter: Optional[str] = None,
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
    ) -> Dict:
        """
        Get disk drives report.

        Args:
            device_filter (str, optional): Device filter
            timestamp_filter (str, optional): Monitoring timestamp filter
            cursor (str, optional): Cursor name for pagination
            page_size (int, optional): Limit number of records per page

        Returns:
            Dict: Disk drives report with cursor and results
        """
        params = {}
        if device_filter:
            params["df"] = device_filter
        if timestamp_filter:
            params["ts"] = timestamp_filter
        if cursor:
            params["cursor"] = cursor
        if page_size:
            params["pageSize"] = str(page_size)

        return self._request("GET", "/v2/queries/disks", params=params)

    def query_logged_on_users(
        self,
        device_filter: Optional[str] = None,
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
    ) -> Dict:
        """
        Get last logged-on users report.

        Args:
            device_filter (str, optional): Device filter
            cursor (str, optional): Cursor name for pagination
            page_size (int, optional): Limit number of records per page (10-10000, default 1000)

        Returns:
            Dict: Logged-on users report with cursor and results
        """
        params = {}
        if device_filter:
            params["df"] = device_filter
        if cursor:
            params["cursor"] = cursor
        if page_size:
            params["pageSize"] = str(page_size)

        return self._request("GET", "/v2/queries/logged-on-users", params=params)

    def query_network_interfaces(
        self,
        device_filter: Optional[str] = None,
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
    ) -> Dict:
        """
        Get network interfaces report.

        Args:
            device_filter (str, optional): Device filter
            cursor (str, optional): Cursor name for pagination
            page_size (int, optional): Limit number of records per page

        Returns:
            Dict: Network interfaces report with cursor and results
        """
        params = {}
        if device_filter:
            params["df"] = device_filter
        if cursor:
            params["cursor"] = cursor
        if page_size:
            params["pageSize"] = str(page_size)

        return self._request("GET", "/v2/queries/network-interfaces", params=params)

    def query_raid_drives(
        self,
        device_filter: Optional[str] = None,
        timestamp_filter: Optional[str] = None,
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
    ) -> Dict:
        """
        Get RAID drives report.

        Args:
            device_filter (str, optional): Device filter
            timestamp_filter (str, optional): Monitoring timestamp filter
            cursor (str, optional): Cursor name for pagination
            page_size (int, optional): Limit number of records per page

        Returns:
            Dict: RAID drives report with cursor and results
        """
        params = {}
        if device_filter:
            params["df"] = device_filter
        if timestamp_filter:
            params["ts"] = timestamp_filter
        if cursor:
            params["cursor"] = cursor
        if page_size:
            params["pageSize"] = str(page_size)

        return self._request("GET", "/v2/queries/raid-drives", params=params)

    def query_volumes(
        self,
        device_filter: Optional[str] = None,
        timestamp_filter: Optional[str] = None,
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
        include: Optional[str] = None,
    ) -> Dict:
        """
        Get disk volumes report.

        Args:
            device_filter (str, optional): Device filter
            timestamp_filter (str, optional): Monitoring timestamp filter
            cursor (str, optional): Cursor name for pagination
            page_size (int, optional): Limit number of records per page
            include (str, optional): Additional information to include (bl - BitLocker status)

        Returns:
            Dict: Disk volumes report with cursor and results
        """
        params = {}
        if device_filter:
            params["df"] = device_filter
        if timestamp_filter:
            params["ts"] = timestamp_filter
        if cursor:
            params["cursor"] = cursor
        if page_size:
            params["pageSize"] = str(page_size)
        if include:
            params["include"] = include

        return self._request("GET", "/v2/queries/volumes", params=params)

    def query_processors(
        self,
        device_filter: Optional[str] = None,
        timestamp_filter: Optional[str] = None,
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
    ) -> Dict:
        """
        Get processors report.

        Args:
            device_filter (str, optional): Device filter
            timestamp_filter (str, optional): Monitoring timestamp filter
            cursor (str, optional): Cursor name for pagination
            page_size (int, optional): Limit number of records per page

        Returns:
            Dict: Processors report with cursor and results
        """
        params = {}
        if device_filter:
            params["df"] = device_filter
        if timestamp_filter:
            params["ts"] = timestamp_filter
        if cursor:
            params["cursor"] = cursor
        if page_size:
            params["pageSize"] = str(page_size)

        return self._request("GET", "/v2/queries/processors", params=params)

    def query_software(
        self,
        device_filter: Optional[str] = None,
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
        installed_before: Optional[str] = None,
        installed_after: Optional[str] = None,
    ) -> Dict:
        """
        Get software inventory report.

        Args:
            device_filter (str, optional): Device filter
            cursor (str, optional): Cursor name for pagination
            page_size (int, optional): Limit number of records per page
            installed_before (str, optional): Include software installed before specified date
            installed_after (str, optional): Include software installed after specified date

        Returns:
            Dict: Software inventory report with cursor and results
        """
        params = {}
        if device_filter:
            params["df"] = device_filter
        if cursor:
            params["cursor"] = cursor
        if page_size:
            params["pageSize"] = str(page_size)
        if installed_before:
            params["installedBefore"] = installed_before
        if installed_after:
            params["installedAfter"] = installed_after

        return self._request("GET", "/v2/queries/software", params=params)

    # Additional missing query endpoints
    def query_antivirus_status(
        self,
        device_filter: Optional[str] = None,
        timestamp_filter: Optional[str] = None,
        product_state: Optional[str] = None,
        product_name: Optional[str] = None,
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
    ) -> Dict:
        """
        Get antivirus status report.

        Args:
            device_filter (str, optional): Device filter
            timestamp_filter (str, optional): Monitoring timestamp filter
            product_state (str, optional): Product State filter
            product_name (str, optional): Product Name filter
            cursor (str, optional): Cursor name for pagination
            page_size (int, optional): Limit number of records per page

        Returns:
            Dict: Antivirus status report with cursor and results
        """
        params = {}
        if device_filter:
            params["df"] = device_filter
        if timestamp_filter:
            params["ts"] = timestamp_filter
        if product_state:
            params["productState"] = product_state
        if product_name:
            params["productName"] = product_name
        if cursor:
            params["cursor"] = cursor
        if page_size:
            params["pageSize"] = str(page_size)

        return self._request("GET", "/v2/queries/antivirus-status", params=params)

    def query_antivirus_threats(
        self,
        device_filter: Optional[str] = None,
        timestamp_filter: Optional[str] = None,
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
    ) -> Dict:
        """
        Get antivirus threats report.

        Args:
            device_filter (str, optional): Device filter
            timestamp_filter (str, optional): Monitoring timestamp filter
            cursor (str, optional): Cursor name for pagination
            page_size (int, optional): Limit number of records per page

        Returns:
            Dict: Antivirus threats report with cursor and results
        """
        params = {}
        if device_filter:
            params["df"] = device_filter
        if timestamp_filter:
            params["ts"] = timestamp_filter
        if cursor:
            params["cursor"] = cursor
        if page_size:
            params["pageSize"] = str(page_size)

        return self._request("GET", "/v2/queries/antivirus-threats", params=params)

    def query_custom_fields(
        self,
        device_filter: Optional[str] = None,
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
        updated_after: Optional[str] = None,
        fields: Optional[str] = None,
        show_secure_values: Optional[bool] = None,
    ) -> Dict:
        """
        Get custom fields report.

        Args:
            device_filter (str, optional): Device filter
            cursor (str, optional): Cursor name for pagination
            page_size (int, optional): Limit number of records per page (10-10000, default 1000)
            updated_after (str, optional): Custom fields updated after specified date
            fields (str, optional): Comma-separated list of fields
            show_secure_values (bool, optional): Return secure values as plain text

        Returns:
            Dict: Custom fields report with cursor and results
        """
        params = {}
        if device_filter:
            params["df"] = device_filter
        if cursor:
            params["cursor"] = cursor
        if page_size:
            params["pageSize"] = str(page_size)
        if updated_after:
            params["updatedAfter"] = updated_after
        if fields:
            params["fields"] = fields
        if show_secure_values is not None:
            params["showSecureValues"] = str(show_secure_values).lower()

        return self._request("GET", "/v2/queries/custom-fields", params=params)

    def query_custom_fields_detailed(
        self,
        device_filter: Optional[str] = None,
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
        updated_after: Optional[str] = None,
        fields: Optional[str] = None,
        show_secure_values: Optional[bool] = None,
    ) -> Dict:
        """
        Get custom fields detailed report with additional information about each field.

        Args:
            device_filter (str, optional): Device filter
            cursor (str, optional): Cursor name for pagination
            page_size (int, optional): Limit number of records per page (10-10000, default 1000)
            updated_after (str, optional): Custom fields updated after specified date
            fields (str, optional): Comma-separated list of fields
            show_secure_values (bool, optional): Return secure values as plain text

        Returns:
            Dict: Custom fields detailed report with cursor and results
        """
        params = {}
        if device_filter:
            params["df"] = device_filter
        if cursor:
            params["cursor"] = cursor
        if page_size:
            params["pageSize"] = str(page_size)
        if updated_after:
            params["updatedAfter"] = updated_after
        if fields:
            params["fields"] = fields
        if show_secure_values is not None:
            params["showSecureValues"] = str(show_secure_values).lower()

        return self._request("GET", "/v2/queries/custom-fields-detailed", params=params)

    def query_backup_usage(
        self,
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
        include_deleted_devices: Optional[bool] = None,
    ) -> Dict:
        """
        Get device backup usage report.

        Args:
            cursor (str, optional): Cursor name for pagination
            page_size (int, optional): Limit number of records per page
            include_deleted_devices (bool, optional): Whether to include deleted devices

        Returns:
            Dict: Device backup usage report with cursor and results
        """
        params = {}
        if cursor:
            params["cursor"] = cursor
        if page_size:
            params["pageSize"] = str(page_size)
        if include_deleted_devices is not None:
            params["includeDeletedDevices"] = str(include_deleted_devices).lower()

        return self._request("GET", "/v2/queries/backup/usage", params=params)

    def query_software_patches(
        self,
        device_filter: Optional[str] = None,
        timestamp_filter: Optional[str] = None,
        status: Optional[str] = None,
        product_identifier: Optional[str] = None,
        patch_type: Optional[str] = None,
        impact: Optional[str] = None,
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
    ) -> Dict:
        """
        Get pending, failed and rejected software patches report.

        Args:
            device_filter (str, optional): Device filter
            timestamp_filter (str, optional): Monitoring timestamp filter
            status (str, optional): Patch Status filter
            product_identifier (str, optional): Product Identifier
            patch_type (str, optional): Patch Type filter
            impact (str, optional): Patch Impact filter
            cursor (str, optional): Cursor name for pagination
            page_size (int, optional): Limit number of records per page

        Returns:
            Dict: Software patches report with cursor and results
        """
        params = {}
        if device_filter:
            params["df"] = device_filter
        if timestamp_filter:
            params["ts"] = timestamp_filter
        if status:
            params["status"] = status
        if product_identifier:
            params["productIdentifier"] = product_identifier
        if patch_type:
            params["type"] = patch_type
        if impact:
            params["impact"] = impact
        if cursor:
            params["cursor"] = cursor
        if page_size:
            params["pageSize"] = str(page_size)

        return self._request("GET", "/v2/queries/software-patches", params=params)

    def query_policy_overrides(
        self,
        device_filter: Optional[str] = None,
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
    ) -> Dict:
        """
        Get summary of device policy overrides.

        Args:
            device_filter (str, optional): Device filter
            cursor (str, optional): Cursor name for pagination
            page_size (int, optional): Limit number of records per page (10-10000, default 1000)

        Returns:
            Dict: Policy overrides report with cursor and results
        """
        params = {}
        if device_filter:
            params["df"] = device_filter
        if cursor:
            params["cursor"] = cursor
        if page_size:
            params["pageSize"] = str(page_size)

        return self._request("GET", "/v2/queries/policy-overrides", params=params)

    def query_scoped_custom_fields(
        self,
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
        updated_after: Optional[str] = None,
        fields: Optional[str] = None,
        scopes: Optional[str] = None,
        show_secure_values: Optional[bool] = None,
    ) -> Dict:
        """
        Get scoped custom fields report for different scopes (device, location, organization).

        Args:
            cursor (str, optional): Cursor name for pagination
            page_size (int, optional): Limit number of records per page (10-10000, default 1000)
            updated_after (str, optional): Custom fields updated after specified date
            fields (str, optional): Comma-separated list of fields
            scopes (str, optional): Comma-separated list of scopes (default: all)
            show_secure_values (bool, optional): Return secure values as plain text

        Returns:
            Dict: Scoped custom fields report with cursor and results
        """
        params = {}
        if cursor:
            params["cursor"] = cursor
        if page_size:
            params["pageSize"] = str(page_size)
        if updated_after:
            params["updatedAfter"] = updated_after
        if fields:
            params["fields"] = fields
        if scopes:
            params["scopes"] = scopes
        if show_secure_values is not None:
            params["showSecureValues"] = str(show_secure_values).lower()

        return self._request("GET", "/v2/queries/scoped-custom-fields", params=params)

    def query_scoped_custom_fields_detailed(
        self,
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
        updated_after: Optional[str] = None,
        fields: Optional[str] = None,
        scopes: Optional[str] = None,
        show_secure_values: Optional[bool] = None,
    ) -> Dict:
        """
        Get scoped custom fields detailed report with additional information about each field.

        Args:
            cursor (str, optional): Cursor name for pagination
            page_size (int, optional): Limit number of records per page (10-10000, default 1000)
            updated_after (str, optional): Custom fields updated after specified date
            fields (str, optional): Comma-separated list of fields
            scopes (str, optional): Comma-separated list of scopes (default: all)
            show_secure_values (bool, optional): Return secure values as plain text

        Returns:
            Dict: Scoped custom fields detailed report with cursor and results
        """
        params = {}
        if cursor:
            params["cursor"] = cursor
        if page_size:
            params["pageSize"] = str(page_size)
        if updated_after:
            params["updatedAfter"] = updated_after
        if fields:
            params["fields"] = fields
        if scopes:
            params["scopes"] = scopes
        if show_secure_values is not None:
            params["showSecureValues"] = str(show_secure_values).lower()

        return self._request(
            "GET", "/v2/queries/scoped-custom-fields-detailed", params=params
        )

    # Device management and maintenance functions
    def schedule_device_maintenance(
        self,
        device_id: int,
        end: float,
        start: Optional[float] = None,
        disabled_features: Optional[List[str]] = None,
    ) -> None:
        """
        Schedule maintenance window for device.

        Args:
            device_id (int): Device identifier
            end (float): Maintenance window end time (epoch seconds)
            start (float, optional): Maintenance window start time (defaults to now)
            disabled_features (List[str], optional): Features to disable during maintenance
                                                   (ALERTS, PATCHING, AVSCANS, TASKS)
        """
        # Validate disabled_features if provided
        if disabled_features:
            valid_features = {"ALERTS", "PATCHING", "AVSCANS", "TASKS"}
            invalid_features = set(disabled_features) - valid_features
            if invalid_features:
                raise NinjaRMMValidationError(
                    f"Invalid disabled features: {invalid_features}. "
                    f"Valid features are: {valid_features}",
                    "disabled_features",
                )

        data: Dict[str, Any] = {"end": end}
        if start is not None:
            data["start"] = start
        if disabled_features:
            data["disabledFeatures"] = disabled_features

        return self._request("PUT", f"/v2/device/{device_id}/maintenance", json=data)

    def cancel_device_maintenance(self, device_id: int) -> None:
        """
        Cancel pending or active maintenance for device.

        Args:
            device_id (int): Device identifier
        """
        return self._request("DELETE", f"/v2/device/{device_id}/maintenance")

    def control_windows_service_advanced(
        self,
        device_id: int,
        service_id: str,
        action: Literal["START", "PAUSE", "STOP", "RESTART"],
    ) -> None:
        """
        Start/Stop/Restart/Pause Windows Service on a device.

        Args:
            device_id (int): Device identifier
            service_id (str): Service identifier
            action (str): Action to perform (START, PAUSE, STOP, RESTART)
        """
        if action not in ("START", "PAUSE", "STOP", "RESTART"):
            raise NinjaRMMValidationError(
                "Invalid service control action. Must be START, PAUSE, STOP, or RESTART",
                "action",
            )

        data = {"action": action}
        return self._request(
            "POST",
            f"/v2/device/{device_id}/windows-service/{service_id}/control",
            json=data,
        )

    # Patch management functions
    def run_os_patch_apply(self, device_id: int) -> None:
        """
        Submit a job to start a device OS patch apply.

        Args:
            device_id (int): Device identifier
        """
        return self._request("POST", f"/v2/device/{device_id}/patch/os/apply")

    def run_os_patch_scan(self, device_id: int) -> None:
        """
        Submit a job to start a device OS patch scan.

        Args:
            device_id (int): Device identifier
        """
        return self._request("POST", f"/v2/device/{device_id}/patch/os/scan")

    def run_software_patch_apply(self, device_id: int) -> None:
        """
        Submit a job to start a device software patch apply.

        Args:
            device_id (int): Device identifier
        """
        return self._request("POST", f"/v2/device/{device_id}/patch/software/apply")

    def run_software_patch_scan(self, device_id: int) -> None:
        """
        Submit a job to start a device software patch scan.

        Args:
            device_id (int): Device identifier
        """
        return self._request("POST", f"/v2/device/{device_id}/patch/software/scan")

    # Group management functions
    def get_group_device_ids(self, group_id: int) -> List[int]:
        """
        Get list of device identifiers that match group criteria.

        Args:
            group_id (int): Group identifier

        Returns:
            List[int]: List of device identifiers
        """
        return self._request("GET", f"/v2/group/{group_id}/device-ids")

    # Backup functions
    def get_backup_jobs(
        self,
        device_filter: Optional[str] = None,
        deleted_device_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
        plan_type_filter: Optional[str] = None,
        start_time_filter: Optional[str] = None,
        include: Optional[str] = None,
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
    ) -> Dict:
        """
        Get list of backup jobs.

        Args:
            device_filter (str, optional): Device filter
            deleted_device_filter (str, optional): Deleted device filter
            status_filter (str, optional): Backup job status filter
            plan_type_filter (str, optional): Backup job planType filter
            start_time_filter (str, optional): Backup job startTime filter
            include (str, optional): Which devices to include (active|deleted|all, default: active)
            cursor (str, optional): Cursor name for pagination
            page_size (int, optional): Limit number of records per page (1-10000, default: 10000)

        Returns:
            Dict: Backup jobs report with cursor and results
        """
        params = {}
        if device_filter:
            params["df"] = device_filter
        if deleted_device_filter:
            params["ddf"] = deleted_device_filter
        if status_filter:
            params["sf"] = status_filter
        if plan_type_filter:
            params["ptf"] = plan_type_filter
        if start_time_filter:
            params["stf"] = start_time_filter
        if include:
            params["include"] = include
        if cursor:
            params["cursor"] = cursor
        if page_size:
            params["pageSize"] = str(page_size)

        return self._request("GET", "/v2/backup/jobs", params=params)

    # Document template functions
    def get_document_template(
        self, template_id: int, include_technician_roles: Optional[bool] = None
    ) -> Dict:
        """
        Get document template by ID.

        Args:
            template_id (int): Document template identifier
            include_technician_roles (bool, optional): Include allowed technician roles

        Returns:
            Dict: Document template details
        """
        params = {}
        if include_technician_roles is not None:
            params["includeTechnicianRoles"] = str(include_technician_roles).lower()

        return self._request(
            "GET", f"/v2/document-templates/{template_id}", params=params
        )

    def delete_document_template(self, template_id: int) -> None:
        """
        Delete a document template by ID.

        Args:
            template_id (int): Document template identifier
        """
        return self._request("DELETE", f"/v2/document-templates/{template_id}")

    # Ticketing functions
    def get_ticket_attributes(self) -> List[Dict]:
        """
        Get list of ticket attributes.

        Returns:
            List[Dict]: List of ticket attribute objects
        """
        return self._request("GET", "/v2/ticketing/attributes")

    def get_contacts(self) -> List[Dict]:
        """
        Get list of contacts.

        Returns:
            List[Dict]: List of contact objects
        """
        return self._request("GET", "/v2/ticketing/contact/contacts")

    def get_ticket_forms(self) -> List[Dict]:
        """
        Get list of ticket forms with their fields.

        Returns:
            List[Dict]: List of ticket form objects
        """
        return self._request("GET", "/v2/ticketing/ticket-form")

    def get_ticket_statuses(self) -> List[Dict]:
        """
        Get list of ticket statuses.

        Returns:
            List[Dict]: List of ticket status objects
        """
        return self._request("GET", "/v2/ticketing/statuses")

    # Enhanced organization and location management
    # Note: delete_organization method already exists earlier in the class

    def _paginate_with_after(
        self, method_func: Callable, page_size: int = 100, **kwargs: Any
    ) -> Generator[Dict, None, None]:
        """
        Generic pagination helper for endpoints that use 'after' parameter.

        Args:
            method_func: The method to call for each page
            page_size: Number of items per page
            **kwargs: Additional arguments to pass to the method

        Yields:
            Dict: Each item from the paginated results
        """
        after = None

        while True:
            logger.info(f"Fetching page with page_size={page_size}, after={after}")

            # Call the method with current pagination parameters
            page_results = method_func(page_size=page_size, after=after, **kwargs)

            # If no results, we're done
            if not page_results:
                break

            # Yield each item from this page
            for item in page_results:
                yield item

            # If we got fewer results than page_size, we're done
            if len(page_results) < page_size:
                break

            # Get the last ID for the next page
            after = page_results[-1].get("id")
            if after is None:
                logger.warning(
                    "No 'id' field found in last item, pagination may not work correctly"
                )
                break

    def _paginate_with_cursor(
        self, method_func: Callable, page_size: int = 100, **kwargs: Any
    ) -> Generator[Dict, None, None]:
        """
        Generic pagination helper for endpoints that use 'cursor' parameter.

        Args:
            method_func: The method to call for each page
            page_size: Number of items per page
            **kwargs: Additional arguments to pass to the method

        Yields:
            Dict: Each item from the paginated results
        """
        cursor = None

        while True:
            logger.info(f"Fetching page with page_size={page_size}, cursor={cursor}")

            # Call the method with current pagination parameters
            response = method_func(page_size=page_size, cursor=cursor, **kwargs)

            # Handle the response structure for cursor-based endpoints
            if not isinstance(response, dict):
                logger.error("Expected dict response for cursor-based pagination")
                break

            # Get the results from the response
            results = response.get("results", [])
            if not results:
                break

            # Yield each item from this page
            for item in results:
                yield item

            # Get cursor information for next page
            cursor_info = response.get("cursor", {})

            # Check if we have more pages
            if not cursor_info:
                break

            # Get the cursor name for the next page
            cursor = cursor_info.get("name")
            if not cursor:
                break

            # If count is less than page_size, we might be done
            count = cursor_info.get("count", 0)
            if count < page_size:
                logger.info(
                    f"Received {count} items, less than page_size {page_size}, likely last page"
                )

    def _get_all_with_after(
        self, method_func: Callable, page_size: int = 100, **kwargs: Any
    ) -> List[Dict]:
        """
        Get all items from an endpoint that uses 'after' pagination.

        Args:
            method_func: The method to call for each page
            page_size: Number of items per page
            **kwargs: Additional arguments to pass to the method

        Returns:
            List[Dict]: All items from all pages
        """
        return list(
            self._paginate_with_after(method_func, page_size=page_size, **kwargs)
        )

    def _get_all_with_cursor(
        self, method_func: Callable, page_size: int = 100, **kwargs: Any
    ) -> List[Dict]:
        """
        Get all items from an endpoint that uses 'cursor' pagination.

        Args:
            method_func: The method to call for each page
            page_size: Number of items per page
            **kwargs: Additional arguments to pass to the method

        Returns:
            List[Dict]: All items from all pages
        """
        return list(
            self._paginate_with_cursor(method_func, page_size=page_size, **kwargs)
        )

    # =========================================================================
    # Asset Tags API
    # =========================================================================

    def get_tags(self) -> Dict:
        """
        Get a list of all asset tags.

        Returns:
            Dict: Response containing a 'tags' key with list of tag objects.
                Each tag object contains:
                - id (int): Tag ID
                - name (str): Tag name
                - description (str): Description of the tag
                - createTime (float): Creation time in seconds since unix epoch
                - updateTime (float): Last update time in seconds since unix epoch
                - createdByUserId (int): ID of the user that created the tag
                - updatedByUserId (int): ID of the user that last updated the tag
                - targetsCount (int): Number of assets with this tag
                - createdBy (dict): User info (id, name, email) who created the tag
                - updatedBy (dict): User info (id, name, email) who last updated the tag

        Raises:
            NinjaRMMAuthError: If authentication fails
            NinjaRMMAPIError: If the API request fails
        """
        return self._request("GET", "/v2/tag")

    def create_tag(
        self,
        name: str,
        description: Optional[str] = None,
    ) -> Dict:
        """
        Create a new asset tag.

        Args:
            name: Tag name (1-40 characters)
            description: Tag description (0-250 characters, optional)

        Returns:
            Dict: Created tag object containing:
                - id (int): Tag ID
                - name (str): Tag name
                - description (str): Description of the tag
                - createTime (float): Creation time in seconds since unix epoch
                - updateTime (float): Last update time in seconds since unix epoch
                - createdByUserId (int): ID of the user that created the tag
                - updatedByUserId (int): ID of the user that last updated the tag

        Raises:
            NinjaRMMAuthError: If authentication fails
            NinjaRMMValidationError: If name is invalid (empty or > 40 chars)
            NinjaRMMAPIError: If the API request fails
        """
        data: Dict[str, Any] = {"name": name}
        if description is not None:
            data["description"] = description

        return self._request("POST", "/v2/tag", json=data)

    def update_tag(
        self,
        tag_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict:
        """
        Update an existing asset tag.

        Args:
            tag_id: ID of the tag to update
            name: New tag name (0-40 characters, optional)
            description: New tag description (0-250 characters, optional)

        Returns:
            Dict: Updated tag object containing:
                - id (int): Tag ID
                - name (str): Tag name
                - description (str): Description of the tag
                - createTime (float): Creation time in seconds since unix epoch
                - updateTime (float): Last update time in seconds since unix epoch
                - createdByUserId (int): ID of the user that created the tag
                - updatedByUserId (int): ID of the user that last updated the tag

        Raises:
            NinjaRMMAuthError: If authentication fails
            NinjaRMMValidationError: If parameters are invalid
            NinjaRMMAPIError: If the API request fails
                - 404: Tag not found
        """
        data: Dict[str, Any] = {}
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description

        return self._request("PUT", f"/v2/tag/{tag_id}", json=data)

    def delete_tag(self, tag_id: int) -> None:
        """
        Delete a single asset tag.

        Args:
            tag_id: ID of the tag to delete

        Raises:
            NinjaRMMAuthError: If authentication fails
            NinjaRMMAPIError: If the API request fails
                - 404: Tag not found
        """
        self._request("DELETE", f"/v2/tag/{tag_id}")

    def delete_tags(self, tag_ids: List[int]) -> None:
        """
        Delete multiple asset tags at once.

        Args:
            tag_ids: List of tag IDs to delete

        Raises:
            NinjaRMMAuthError: If authentication fails
            NinjaRMMValidationError: If tag_ids is empty or invalid
            NinjaRMMAPIError: If the API request fails
        """
        self._request("POST", "/v2/tag/delete", json=tag_ids)

    def merge_tags(
        self,
        tag_ids: List[int],
        merge_method: Literal["MERGE_INTO_EXISTING_TAG", "MERGE_INTO_NEW_TAG"],
        merge_into_tag_id: Optional[int] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict:
        """
        Merge multiple tags into one existing or new tag.

        When merging into an existing tag, provide merge_into_tag_id.
        When creating a new tag, provide name (and optionally description).

        Args:
            tag_ids: List of tag IDs to merge
            merge_method: Either "MERGE_INTO_EXISTING_TAG" or "MERGE_INTO_NEW_TAG"
            merge_into_tag_id: Target tag ID (required when merge_method is
                "MERGE_INTO_EXISTING_TAG")
            name: New tag name (required when merge_method is "MERGE_INTO_NEW_TAG",
                0-40 characters)
            description: New tag description (optional, 0-250 characters)

        Returns:
            Dict: Resulting tag object containing:
                - id (int): Tag ID
                - name (str): Tag name
                - description (str): Description of the tag
                - createTime (float): Creation time in seconds since unix epoch
                - updateTime (float): Last update time in seconds since unix epoch
                - createdByUserId (int): ID of the user that created the tag
                - updatedByUserId (int): ID of the user that last updated the tag

        Raises:
            NinjaRMMAuthError: If authentication fails
            NinjaRMMValidationError: If required parameters are missing
            NinjaRMMAPIError: If the API request fails
                - 404: Tag not found
        """
        data: Dict[str, Any] = {
            "tagIds": tag_ids,
            "mergeMethod": merge_method,
        }
        if merge_into_tag_id is not None:
            data["mergeIntoTagId"] = merge_into_tag_id
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description

        return self._request("POST", "/v2/tag/merge", json=data)

    def batch_tag_assets(
        self,
        asset_type: Literal["device"],
        asset_ids: List[int],
        tag_ids_to_add: Optional[List[int]] = None,
        tag_ids_to_remove: Optional[List[int]] = None,
    ) -> None:
        """
        Batch add and/or remove tags from multiple assets.

        Args:
            asset_type: Type of asset (currently only "device" is supported)
            asset_ids: List of asset IDs to modify
            tag_ids_to_add: List of tag IDs to add to the assets (optional)
            tag_ids_to_remove: List of tag IDs to remove from the assets (optional)

        Raises:
            NinjaRMMAuthError: If authentication fails
            NinjaRMMValidationError: If parameters are invalid
            NinjaRMMAPIError: If the API request fails
        """
        data: Dict[str, Any] = {"assetIds": asset_ids}
        if tag_ids_to_add is not None:
            data["tagIdsToAdd"] = tag_ids_to_add
        if tag_ids_to_remove is not None:
            data["tagIdsToRemove"] = tag_ids_to_remove

        self._request("POST", f"/v2/tag/{asset_type}", json=data)

    def set_asset_tags(
        self,
        asset_type: Literal["device"],
        asset_id: int,
        tag_ids: List[int],
    ) -> None:
        """
        Set the exact tags for a specific asset.

        This replaces all existing tags on the asset with the provided tag IDs.

        Args:
            asset_type: Type of asset (currently only "device" is supported)
            asset_id: ID of the asset to update
            tag_ids: List of tag IDs to assign to the asset. Existing tags
                on the asset will be removed.

        Raises:
            NinjaRMMAuthError: If authentication fails
            NinjaRMMValidationError: If parameters are invalid
            NinjaRMMAPIError: If the API request fails
                - 404: Asset not found
        """
        data: Dict[str, Any] = {"tagIds": tag_ids}
        self._request("PUT", f"/v2/tag/{asset_type}/{asset_id}", json=data)
