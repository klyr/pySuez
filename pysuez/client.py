import requests
import re
import datetime

BASE_URI = 'https://www.toutsurmoneau.fr'
API_ENDPOINT_LOGIN = 'mon-compte-en-ligne/je-me-connecte'
API_ENDPOINT_DATA = 'mon-compte-en-ligne/statJData'
API_ENDPOINT_HISTORY = 'mon-compte-en-ligne/statMData'

class PySuezError(Exception):
    pass

class SuezClient():
    """Global variables."""

    def __init__(self, username, password, counter_id, session=None, timeout=None):
        """Initialize the client object."""
        self._username = username
        self._password = password
        self._counter_id = counter_id
        self._token = ''
        self.attributes = {}
        self.success = False
        self._session = session or requests.session()
        self._timeout = timeout
        self.state = 0

    def _get_token(self):
        """Get the token"""

        url = f'{BASE_URI}/{API_ENDPOINT_LOGIN}'

        response = self._session.get(url, timeout=self._timeout)

        phrase = re.compile('_csrf_token" value="(.*)" />')
        result = phrase.search(response.content.decode('utf-8'))
        self._token = result.group(1)

    def _login(self):
        """Connect and get the cookie"""
        self._get_token()
        data = {
            '_username': self._username,
            '_password': self._password,
            '_csrf_token': self._token,
            'signin[username]': self._username,
            'signin[password]': None,
            'tsme_user_login[_username]': self._username,
            'tsme_user_login[_password]': self._password
        }
        url = f'{BASE_URI}/{API_ENDPOINT_LOGIN}'
        try:
            self._session.post(url,
                               data=data,
                               allow_redirects=False,
                               timeout=self._timeout)
        except OSError:
            raise PySuezError("Can not submit login form.")

        if not 'eZSESSID' in self._session.cookies.get_dict():
            raise PySuezError("Login error: Please check your username/password.")
        
        return True

    def _fetch_data(self, date):
        year = date.strftime('%Y')
        month = date.strftime('%m')

        url = f'{BASE_URI}/{API_ENDPOINT_DATA}/{year}/{month}/{self._counter_id}'
        data = self._session.get(url)
        data.raise_for_status()

        return data.json()

    def _fetch_history(self):
        url = f'{BASE_URI}/{API_ENDPOINT_HISTORY}/{self._counter_id}'
        data = self._session.get(url)
        data.raise_for_status()

        return data.json()

    def _fetch_all_data(self):
        """Fetch latest data from Suez."""
        today = datetime.date.today()
        previous_month = today.replace(day=1) - datetime.timedelta(days=1)
        
        self._login()

        self.attributes['attribution'] = "Data provided by toutsurmoneau.fr"

        try:
            this_month_data = self._fetch_data(today)
            self.state = int(this_month_data[-1][1] * 1000)
            self.success = True
            self.attributes['thisMonthConsumption'] = { date: int(consumption * 1000) for [date, consumption, *_] in this_month_data }
        except ValueError:
            raise PySuezError("Issue with this month data")

        try:
            previous_month_data = self._fetch_data(previous_month)
            self.attributes['previousMonthConsumption'] = { date: int(consumption * 1000) for [date, consumption, *_] in previous_month_data }
        except ValueError:
            raise PySuezError("Issue with previous month data")

        try:
            data = self._fetch_history()
            history_data = data[:-3]
            [year_overall, last_year_overall, highest] = data[-3:]

            self.attributes['highestMonthlyConsumption'] = int(highest * 1000)
            self.attributes['lastYearOverAll'] = int(last_year_overall * 1000)
            self.attributes['thisYearOverAll'] = int(year_overall * 1000)
            self.attributes['history'] = { date: int(consumption * 1000) for [_, consumption, _, date, *_] in history_data }
        except ValueError:
            raise PySuezError("Issue with history data")

    def update(self):
        """Return the latest collected data from toutsurmoneau.fr."""
        self._fetch_all_data()
        if not self.success:
            return
        return self.attributes
        
    def close_session(self):
        """Close current session."""
        self._session.close()
        self._session = None
