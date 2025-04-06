import os
import random
import re
import logging

import attr
import pexpect

# from loguru import logger
from typing import List, Union
from pexpect.exceptions import EOF, ExceptionPexpect
from .exceptions import (
    UnknownVersionException,
    WindscribeNotRunningException,
    WindscribeNotFoundException,
    UnsupportedVersionException,
    NotLoggedInException,
    InvalidLocationException,
    InvalidPasswordException,
    InvalidUsernameException,
    InvalidCredentialsException,
    ProAccountRequiredException,
)

# Set up the basic configuration for logging
logging.basicConfig(
    level=logging.INFO,  # Set the logging level
    format='%(asctime)s - %(levelname)s - %(message)s',  # Define the log message format
    datefmt='%Y-%m-%d %H:%M:%S'  # Define the date format
)

# Create a logger object
logger = logging.getLogger(__name__)

WINDSCRIBE_NOT_RUNNING = "The Windscribe service is not running."
WINDSCRIBE_NOT_FOUND = "The Windscribe CLI cannot be found."
NOT_LOGGED_IN = "Not logged in."
NOT_CONNECTED_TO_INTERNET = "Not connected to internet."
UNSUPPORTED_VERSION = "This module is incompatible with your Windscribe CLI version."

ANSI_SEQUENCES = r"(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]"


@attr.s
class WindscribeLocation:
    """ Represents a Windscribe location. """

    name = attr.ib(type=str)
    abbrev = attr.ib(type=str)
    city = attr.ib(type=str)
    label = attr.ib(type=str)
    pro = attr.ib(type=bool)


@attr.s
class WindscribeStatus:
    """ Represents a Windscribe status. """

    pid = attr.ib(type=int)
    status = attr.ib(type=str)
    uptime = attr.ib(type=str)
    cpu_usage = attr.ib(type=float)
    mem_usage = attr.ib(type=float)
    ip = attr.ib(type=str)
    connected = attr.ib(type=bool)


@attr.s
class WindscribeAccount:
    """ Represents a Windscribe account. """

    username = attr.ib(type=str)
    current_usage = attr.ib(type=float)
    current_usage_unit = attr.ib(type=str)
    max_usage = attr.ib(type=float)
    max_usage_unit = attr.ib(type=str)
    plan = attr.ib(type=str)


def remove_ansi_sequences(text: str) -> str:
    """Remove ansi sequences from a string.

    Args:
    -----
        `text (str)`: The string.

    Returns:
    --------
        `str`: The string without the ansi sequences.
    """
    return re.sub(ANSI_SEQUENCES, "", text)


def execute_command(cmd: str) -> pexpect.spawn:
    """Execute a command.

    Args:
    -----
        `cmd (str)`: The command.

    Raises:
    -------
        `WindscribeNotFoundException`: if the Windscribe CLI cannot be found.

    Returns:
    --------
        `pexpect.spawn`: The child process.
    """
    try:
        logger.info(f"Execute command : {cmd}")

        return pexpect.spawn(cmd, encoding="utf-8", timeout=None)

    except ExceptionPexpect as e:
        logger.error(f"Windscribe CLI is not found. -> {e}")

        raise WindscribeNotFoundException(WINDSCRIBE_NOT_FOUND)


def version() -> str:
    """Gets the version of the Windscribe CLI.

    Raises:
    -------
        `WindscribeNotFoundException`: if the Windscribe CLI cannot be found.
        `UnknownVersionException`: if the Windscribe version cannot be found.

    Returns:
    --------
        `str`: The Windscribe CLI version.
    """
    # Execute the command
    child = execute_command("windscribe")

    # Try to find the version in the output
    match = child.expect([EOF, "Windscribe CLI client"])

    # Wait until the command returns
    child.wait()

    # The version is found
    if match == 1:
        version = re.search(r"v[0-9]{1,}\.[0-9]{1,}",
                            child.readline()).group(0)

        logger.info(f"Windscribe CLI client {version}.")

        return version

    # The version is not found
    else:
        raise UnknownVersionException(
            "The Windscribe version cannot be found.")


def locations() -> List[WindscribeLocation]:
    """Get the list of server locations.

    Raises:
    -------
        `WindscribeNotFoundException`: if the Windscribe CLI cannot be found.
        `WindscribeNotRunningException`: if the Windscribe service is not running.
        `UnsupportedVersionException`: if this module is incompatible with your Windscribe CLI version.
        `NotLoggedInException` : if the user is not logged in.

    Returns:
    --------
        `List[WindscribeLocation]`: The list of server locations.
    """
    # Execute the command
    child = execute_command("windscribe locations")

    # Read the output
    match = child.expect(
        [
            re.compile(
                "Location[ ]{2,}Short Name[ ]{2,}City Name[ ]{2,}Label[ ]{2,}Pro[ ]{0,}(%s){0,}\\r\\n" % ANSI_SEQUENCES
            ),
            "Please login to use Windscribe",
            "Windscribe is not running",
            EOF,
        ]
    )

    # Unsupported version
    if match == 3:
        logger.error(UNSUPPORTED_VERSION)

        raise UnsupportedVersionException(UNSUPPORTED_VERSION)

    # The service is not running
    elif match == 2:
        logger.error(WINDSCRIBE_NOT_RUNNING)

        raise WindscribeNotRunningException(WINDSCRIBE_NOT_RUNNING)

    # The user is not logged in
    elif match == 1:
        logger.warning(NOT_LOGGED_IN)

        raise NotLoggedInException(NOT_LOGGED_IN)

    # Get the locations
    else:
        # Loop for each lines
        locations = []
        for location in child.readlines():

            location_info = re.split(
                "[ ]{2,}", remove_ansi_sequences(location).strip())

            # Check if the location info are valid
            if (len(location_info) != 5 or location_info[4] != "*") and len(location_info) != 4:
                raise UnsupportedVersionException(UNSUPPORTED_VERSION)

            # Add the location
            if len(location_info) == 5:
                location_info[4] = True
            else:
                location_info.append(False)

            locations.append(WindscribeLocation(*location_info))

        return locations


def random_connect():
    """Connect to a random Windscribe server.

    Raises:
    -------
        `WindscribeNotFoundException`: if the Windscribe CLI cannot be found.
        `WindscribeNotRunningException`: if the Windscribe service is not running.
        `UnsupportedVersionException`: if this module is incompatible with your Windscribe CLI version.
        `NotLoggedInException` : if the user is not logged in.
        `InvalidLocationException` : if the location is not valid.
        `ProAccountRequiredException` : if a pro account is required.
        `ConnectionError` : if the user is not connected to internet.
    """
    connect(random.choice(locations()))


def connect(location: Union[str, WindscribeLocation] = "best"):
    """Connect to a Windscribe server.

    Args:
    -----
        `location ([str, WindscribeLocation], optional)`: The Windscribe server location. Defaults to "best".

    Raises:
    -------
        `TypeError`: if location is neither a WindscribeLocation, neither a str.
        `WindscribeNotFoundException`: if the Windscribe CLI cannot be found.
        `WindscribeNotRunningException`: if the Windscribe service is not running.
        `UnsupportedVersionException`: if this module is incompatible with your Windscribe CLI version.
        `NotLoggedInException` : if the user is not logged in.
        `InvalidLocationException` : if the location is not valid.
        `ProAccountRequiredException` : if a pro account is required.
        `ConnectionError` : if the user is not connected to internet.
    """
    # Check the parameter value
    if isinstance(location, WindscribeLocation):
        location = location.label

    elif type(location) is not str:
        raise TypeError(
            "The location parameter must be a str or a WindscribeLocation object.")

    # Execute the command
    child = execute_command(f'windscribe connect "{location}"')

    # Read the output
    match = child.expect(
        [
            "Your IP changed from",
            "IP check after connection failed, you may not have internet",
            "is not a valid location",
            "requires a Pro account",
            "Please login to use Windscribe",
            "Failed to connect",
            "Windscribe is not running",
            EOF,
        ]
    )

    # Unsupported version
    if match == 7:
        logger.error(UNSUPPORTED_VERSION)

        raise UnsupportedVersionException(UNSUPPORTED_VERSION)

    # The service is not running
    elif match == 6:
        logger.error(WINDSCRIBE_NOT_RUNNING)

        raise WindscribeNotRunningException(WINDSCRIBE_NOT_RUNNING)

    # The user needs to be connected to internet
    elif match == 5:
        logger.error(NOT_CONNECTED_TO_INTERNET)

        raise ConnectionError(NOT_CONNECTED_TO_INTERNET)

    # The user is not logged in
    elif match == 4:
        logger.warning(NOT_LOGGED_IN)

        raise NotLoggedInException(NOT_LOGGED_IN)

    # The user needs to be a pro account
    elif match == 3:
        logger.warning(f"{location} requires a Pro account.")

        raise ProAccountRequiredException(
            f"{location} requires a Pro account.")

    # The location is invalid
    elif match == 2:
        logger.warning(f"{location} is not a valid location.")

        raise InvalidLocationException(f"{location} is not a valid location.")

    # The user may not have internet
    elif match == 1:
        # Wait until the command returns
        child.wait()

        logger.info("Connected.")

        logger.warning(
            "IP check after connection failed, you may not have internet")

    # The connection succeed
    else:
        # Wait until the command returns
        child.wait()

        logger.info("Connected.")


def disconnect():
    """Disconnect from the Windscribe server.

    Raises:
    -------
        `WindscribeNotFoundException`: if the Windscribe CLI cannot be found.
        `WindscribeNotRunningException`: if the Windscribe service is not running.
        `UnsupportedVersionException`: if this module is incompatible with your Windscribe CLI version.
        `ConnectionError` : if the user is not connected to internet.
    """
    # Execute the command
    child = execute_command("windscribe disconnect")

    # Read the output
    match = child.expect(
        [
            "DISCONNECTED",
            "Service communication error",
            "Windscribe is not running",
            EOF,
        ]
    )

    # Unsupported version
    if match == 3:
        logger.error(UNSUPPORTED_VERSION)

        raise UnsupportedVersionException(UNSUPPORTED_VERSION)

    # The service is not running
    elif match == 2:
        logger.error(WINDSCRIBE_NOT_RUNNING)

        raise WindscribeNotRunningException(WINDSCRIBE_NOT_RUNNING)

    # The user needs to be connected to internet
    elif match == 1:
        logger.error(NOT_CONNECTED_TO_INTERNET)

        raise ConnectionError(NOT_CONNECTED_TO_INTERNET)

    # Disconnected
    else:
        # Wait until the command returns
        child.wait()

        logger.info("Disconnected.")


def login(user: str = None, pw: str = None) -> bool:
    """Login to the Windscribe CLI.

    Args:
    -----
        `user (str, optional)`: The username. Defaults to None.
        `pw (str, optional)`: The password. Defaults to None.

    Raises:
    -------
        `ValueError`: if the password is less than 4 characters long.
        `ConnectionError` : if the user is not connected to internet.
        `InvalidUsernameException`: if the Windscribe username is not in the environement.
        `InvalidPasswordException`: if the Windscribe password is not in the environement.
        `InvalidCredentialsException`: if the credentials are invalid.
        `WindscribeNotFoundException`: if the Windscribe CLI cannot be found.
        `WindscribeNotRunningException`: if the Windscribe service is not running.
        `UnsupportedVersionException`: if this module is incompatible with your Windscribe CLI version.

    Returns:
    --------
        `bool`: True if the user has been logged in, False if the user was already logged in.
    """
    # Get the user
    if user is None:
        user = os.environ.get("WINDSCRIBE_USER")
        if user is None:
            raise InvalidUsernameException(
                "Could not found Windscribe username in environement.")
    user += "\n"

    # Get the password
    if pw is None:
        pw = os.environ.get("WINDSCRIBE_PW")
        if pw is None:
            raise InvalidPasswordException(
                "Could not found Windscribe password in environement.")
    pw += "\n"

    # Value checking
    if len(pw) <= 4:
        raise ValueError(
            "Windscribe password must be at least 4 characters long.")

    # Execute the command
    child = execute_command("windscribe login")
    # Read the output
    match = child.expect(["Windscribe Username:", "Already Logged in", EOF])

    # Unsupported version
    if match == 2:
        logger.error(UNSUPPORTED_VERSION)

        raise UnsupportedVersionException(UNSUPPORTED_VERSION)

    # Already logged in
    elif match == 1:
        logger.warning("Already logged in.")

        return False

    # Not logged in
    else:
        # Send username
        child.sendline(user)

        # Send password
        child.expect("Windscribe Password:")

        child.sendline(pw)

        # Check if the connection was successful
        match = child.expect(
            [
                "Logged In",
                "API Error: Could not log in with provided credentials",
                "Windscribe is not running",
                "API Error: No API Connectivity",
                EOF,
            ]
        )

        # Unsupported version
        if match == 4:
            logger.error(UNSUPPORTED_VERSION)

            raise UnsupportedVersionException(UNSUPPORTED_VERSION)

        # The user is not connected to internet
        elif match == 3:
            logger.error(NOT_CONNECTED_TO_INTERNET)

            raise ConnectionError(NOT_CONNECTED_TO_INTERNET)

        # The service is not running
        elif match == 2:
            logger.error(WINDSCRIBE_NOT_RUNNING)

            raise WindscribeNotRunningException(WINDSCRIBE_NOT_RUNNING)

        # Invalid credentials
        elif match == 1:
            logger.warning("Could not log in with provided credentials.")

            raise InvalidCredentialsException(
                "Could not log in with provided credentials.")

        # Logged in
        else:
            # Wait the end of the commands
            child.wait()

            logger.info("Logged in.")

            return True


def logout() -> bool:
    """Logout from the Windscribe CLI.

    Raises:
    -------
        `WindscribeNotFoundException`: if the Windscribe CLI cannot be found.
        `WindscribeNotRunningException`: if the Windscribe service is not running.
        `UnsupportedVersionException`: if this module is incompatible with your Windscribe CLI version.

    Returns:
    --------
        `bool`: True if the user has been logged out, False if the user was already logged out.
    """
    # Execute the command
    child = execute_command("windscribe logout")

    # Read the output
    match = child.expect(
        [
            "DISCONNECTED",
            "Not logged in",
            "Windscribe is not running",
            EOF,
        ]
    )

    # Unsupported version
    if match == 3:
        logger.error(UNSUPPORTED_VERSION)

        raise UnsupportedVersionException(UNSUPPORTED_VERSION)

    # The service is not running
    elif match == 2:
        logger.error(WINDSCRIBE_NOT_RUNNING)

        raise WindscribeNotRunningException(WINDSCRIBE_NOT_RUNNING)

    # The user is not logged in
    elif match == 1:
        # Wait until the command returns
        child.wait()

        logger.warning(NOT_LOGGED_IN)

        return False

    # The user was logged in
    else:
        # Wait until the command returns
        child.wait()

        logger.info("Logged Out.")

        return True


def status() -> WindscribeStatus:
    """Gets the Windscribe CLI status.

    Raises:
    -------
        `WindscribeNotFoundException`: if the Windscribe CLI cannot be found.
        `WindscribeNotRunningException`: if the Windscribe service is not running.
        `UnsupportedVersionException`: if this module is incompatible with your Windscribe CLI version.
        `ConnectionError` : if the user is not connected to internet.

    Returns:
    --------
        `WindscribeStatus`: The Windscribe status.
    """
    # Execute the command
    child = execute_command("windscribe status")

    # Read the output
    match = child.expect(
        [
            "windscribe --",
            "Windscribe is not running",
            EOF,
        ]
    )

    # Unsupported version
    if match == 2:
        logger.error(UNSUPPORTED_VERSION)

        raise UnsupportedVersionException(UNSUPPORTED_VERSION)

    # The service is not running
    elif match == 1:
        logger.error(WINDSCRIBE_NOT_RUNNING)

        raise WindscribeNotRunningException(WINDSCRIBE_NOT_RUNNING)

    # Get status info
    else:
        line_info = re.split(
            r"[,| ]{0,}[^ ]+: ", remove_ansi_sequences(child.readline()).strip())

        # Check if unsupported version
        if len(line_info) != 6:
            logger.error(UNSUPPORTED_VERSION)

            raise UnsupportedVersionException(UNSUPPORTED_VERSION)

        # Parse info
        pid = int(line_info[1])
        status = line_info[2]
        uptime = line_info[3]
        cpu_usage = float(line_info[4])
        mem_usage = float(line_info[5])

        # Read output
        match = child.expect(["IP:", "Service communication error", EOF])

        # Unsupported version
        if match == 2:
            logger.error(UNSUPPORTED_VERSION)

            raise UnsupportedVersionException(UNSUPPORTED_VERSION)

        # The user needs to be connected to internet
        elif match == 1:
            logger.error(NOT_CONNECTED_TO_INTERNET)

            raise ConnectionError(NOT_CONNECTED_TO_INTERNET)

        # Get ip
        else:
            match = re.findall(
                r"\b((?:[0-9]{1,3}\.){3}[0-9]{1,3})\b", remove_ansi_sequences(child.readline()).strip())

            # Check if unsupported version
            if len(match) == 0:
                logger.error(UNSUPPORTED_VERSION)

                raise UnsupportedVersionException(UNSUPPORTED_VERSION)

            # Parse info
            ip = match[0]

            # Get connected status
            connected = "DISCONNECTED" not in remove_ansi_sequences(
                child.readline())

            # Log
            logger.info(
                f"pid : {pid}, status: {status}, uptime: {uptime}, %cpu: {cpu_usage}, %mem: {mem_usage}")
            logger.info(f"IP : {ip}")
            logger.info("CONNECTED" if connected else "DISCONNECTED")

            # Return status
            return WindscribeStatus(*(pid, status, uptime, cpu_usage, mem_usage, ip, connected))


def account() -> WindscribeAccount:
    """Get Windscribe account informations.

    Raises:
    -------
        `WindscribeNotFoundException`: if the Windscribe CLI cannot be found.
        `WindscribeNotRunningException`: if the Windscribe service is not running.
        `UnsupportedVersionException`: if this module is incompatible with your Windscribe CLI version.
        `ConnectionError` : if the user is not connected to internet.
        `NotLoggedInException` : if the user is not logged in.
    """
    # Execute the command
    child = execute_command("windscribe account")

    # Read the output
    match = child.expect(
        [
            re.compile(
                "[ |-]{0,}My Account[ |-]{0,}(%s){0,}\\r\\n" % ANSI_SEQUENCES),
            "Please login to use Windscribe",
            "Failed to connect",
            "Windscribe is not running",
            EOF,
        ]
    )

    # Unsupported version
    if match == 4:
        logger.error(UNSUPPORTED_VERSION)

        raise UnsupportedVersionException(UNSUPPORTED_VERSION)

    # The service is not running
    elif match == 3:
        logger.error(WINDSCRIBE_NOT_RUNNING)

        raise WindscribeNotRunningException(WINDSCRIBE_NOT_RUNNING)

    # The user needs to be connected to internet
    elif match == 2:
        logger.error(NOT_CONNECTED_TO_INTERNET)

        raise ConnectionError(NOT_CONNECTED_TO_INTERNET)

    # The user is not logged in
    elif match == 1:
        logger.warning(NOT_LOGGED_IN)

        raise NotLoggedInException(NOT_LOGGED_IN)

    # Get account info
    else:
        # Username
        child.expect("Username:")
        username = remove_ansi_sequences(child.readline()).strip()

        # Data usage
        child.expect("Data Usage:")
        line_info = remove_ansi_sequences(child.readline()).strip()
        data_usage = line_info.split(" ")
        if len(data_usage) != 5:
            raise UnsupportedVersionException(UNSUPPORTED_VERSION)

        # Plan
        child.expect("Plan:")
        plan = remove_ansi_sequences(child.readline()).strip()

        # Log
        logger.info(
            f"Username: {username}, Data Usage: {data_usage[0]}{data_usage[1]}/{data_usage[3]}{data_usage[4]}, Plan: {plan}"
        )

        # Return account
        return WindscribeAccount(
            *(username, float(data_usage[0]), data_usage[1], float(data_usage[3]), data_usage[4], plan)
        )