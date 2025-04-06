# Python-Windscribe

## Intro

I had purchased a lifetime subscription to Windscribe a few years ago and 
recently noticed that they had released a CLI. Being interested in web crawling,
I threw together this basic CLI wrapper in an afternoon to use on some of my 
personal projects. I plan on making updates soon to cover more of the CLI.

**NOTE:** *I am in no way affiliated with Windscribe.*

## Install

```bash
$ pip install python-windscribe
```
or
```bash
$ python setup.py install
```

## Usage

### Login

Login by explicitly providing your username & password or export environment
variables `WINDSCRIBE_USER` and `WINDSCRIBE_PW`.

```python
import windscribe

windscribe.login('<user>', '<password>')
```

### Logout

Logout from the Windscribe CLI.

```python
windscribe.logout()
```

### Get locations

Returns a list of `WindscribeLocation` instances; each of which have the
following attributes: `name`, `abbrev`, `city`, and `label`.

```python
location_list = windscribe.locations()
```

### Connect

Connects to the best server by default.

```python
windscribe.connect()
```

**NOTE:** *Calling connect multiple times will just cause the VPN to reconnect
to the specified location.*

Connect to a random location:

```python
windscribe.random_connect()
```

Connect to a specific location using a string:

**NOTE:** *You can use a given location's `name`, `abbrev`, `city`, `label` or `pro`.*

```python
windscribe.connect('BBQ')
```

Connect by passing in a `WindscribeLocation` instance:

```python
def get_barbecue():

    for location in windscribe.locations():

        if location.label == 'BBQ': return location

bbq = get_barbecue()

windscribe.connect(bbq)
```

### Disconnect

Disconnect from the Windscribe server.

```python
windscribe.disconnect()
```

### Account Details

Returns a `WindscribeAccount` instance which has the
following attributes: `username`, `current_usage`, `current_usage_unit`, `max_usage`, `max_usage_unit`, and `plan`.

```python
windscribe.account()
```

### Version

Gets the version of the Windscribe CLI.

```python
windscribe.version()
```

### Status

Returns a `WindscribeStatus` instance which has the
following attributes: `pid`, `status`, `uptime`, `cpu_usage`, `mem_usage`, `ip`, and `connected`.

```python
windscribe.status()
```