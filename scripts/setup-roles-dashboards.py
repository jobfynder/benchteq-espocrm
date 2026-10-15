#!/usr/bin/env python3
"""Sets up Benchteq spec v2 settings in EspoCRM through the REST API.

Creates or updates (safe to run again, it never creates duplicates):
  - the four roles: Manager, Interview Manager, Coordinator, Finance
  - the menu, quick-create list, Calendar entity list, INR currency, India time zone
    and India/US as the first phone-number countries
  - the default dashboard (tabs "Today" and "Money")

It does not create users. To give someone a role, pass --assign.

Usage (admin account; run on staging first):
  export ESPO_URL=https://crm.example.com
  export ESPO_USER=admin
  export ESPO_PASSWORD=...
  python3 scripts/setup-roles-dashboards.py --dry-run
  python3 scripts/setup-roles-dashboards.py \
      --assign priya=Coordinator --assign rahul=Finance

Only Python 3.8+ is needed, no extra packages.
"""
import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

# --------------------------------------------------------------------- roles

CUSTOM_ENTITIES = ['CDeliveryResource', 'CProject', 'CPaymentBlock', 'CTimesheet',
                   'CInterviewSession', 'CPayout', 'CReferrer', 'CProvider']
CORE_ENTITIES = ['Lead', 'Contact', 'Account']

# Retired in v2: nobody sees them, data is kept.
RETIRED = ['Opportunity', 'CServicePackage', 'CSessionLog', 'Case', 'Campaign',
           'KnowledgeBaseArticle', 'KnowledgeBaseCategory', 'TargetList',
           'TargetListCategory']


def acl(create='no', read='no', edit='no', delete='no', stream=None):
    return {
        'create': create, 'read': read, 'edit': edit, 'delete': delete,
        'stream': stream or read,
    }


FULL = acl('yes', 'all', 'all', 'all')
READ = acl('no', 'all', 'no', 'no')
WORK = acl('yes', 'all', 'all', 'no')          # create, read all, edit all
WORK_DEL = acl('yes', 'all', 'all', 'own')     # same, may delete own records
EDIT_ONLY = acl('no', 'all', 'all', 'no')      # cannot create, can edit


OWN = acl('yes', 'own', 'own', 'own')
TEAM_WORK = acl('yes', 'all', 'all', 'own')


def everyday_scopes(level):
    """Core scopes people need every day. EspoCRM gives a role NO access to any scope it
    does not list, so each one is listed. level: full, work or read."""
    full = level == 'full'
    work = level in ('full', 'work')
    return {
        'Task': TEAM_WORK if work else OWN,
        'Meeting': TEAM_WORK if work else OWN,
        'Call': TEAM_WORK if work else OWN,
        'Email': OWN, 'EmailTemplate': WORK if work else READ,
        'EmailTemplateCategory': WORK if work else READ,
        'Document': WORK if work else READ, 'DocumentFolder': WORK if work else READ,
        'Template': READ, 'User': acl('no', 'all', 'no', 'no'),
        'Team': acl('no', 'all', 'no', 'no'),
        'Import': full,
        'Calendar': True, 'Activities': True, 'EmailAccountScope': True,
        'GlobalStream': False, 'Currency': False, 'ExternalAccount': False,
        'Webhook': False, 'WorkingTimeCalendar': False,
    }


def build_roles():
    roles = {}

    manager = {e: FULL for e in CUSTOM_ENTITIES + CORE_ENTITIES}
    roles['Manager'] = {
        'data': manager,
        'permissions': {
            'assignmentPermission': 'all', 'userPermission': 'all',
            'messagePermission': 'all', 'exportPermission': 'yes',
            'massUpdatePermission': 'yes', 'userCalendarPermission': 'all',
            'followerManagementPermission': 'all', 'auditPermission': 'yes',
            'mentionPermission': 'all', 'dataPrivacyPermission': 'yes',
        },
    }

    roles['Interview Manager'] = {
        'data': {
            'Lead': WORK, 'Contact': WORK, 'Account': WORK,
            'CInterviewSession': WORK_DEL,
            'CDeliveryResource': READ, 'CProvider': READ, 'CReferrer': READ,
            'CProject': False, 'CPaymentBlock': False, 'CTimesheet': False,
            'CPayout': False,
        },
        'permissions': {
            'assignmentPermission': 'all', 'userPermission': 'all',
            'messagePermission': 'all', 'exportPermission': 'no',
            'massUpdatePermission': 'yes', 'userCalendarPermission': 'all',
            'mentionPermission': 'all',
        },
    }

    # The team is small and works openly: Coordinators can read everything.
    roles['Coordinator'] = {
        'data': {
            'Lead': WORK, 'Contact': WORK, 'Account': WORK,
            'CDeliveryResource': WORK,
            'CProject': WORK_DEL, 'CPaymentBlock': WORK_DEL,
            'CTimesheet': WORK_DEL, 'CInterviewSession': WORK_DEL,
            'CReferrer': WORK,          # a referral lead needs its Referrer
            'CProvider': READ,
            'CPayout': READ,
        },
        'permissions': {
            'assignmentPermission': 'all', 'userPermission': 'all',
            'messagePermission': 'all', 'exportPermission': 'no',
            'massUpdatePermission': 'yes', 'userCalendarPermission': 'all',
            'mentionPermission': 'all',
        },
    }

    roles['Finance'] = {
        'data': {
            'Lead': READ, 'Contact': READ, 'Account': READ,
            'CDeliveryResource': READ, 'CProvider': READ, 'CReferrer': READ,
            'CProject': READ,
            'CPaymentBlock': EDIT_ONLY, 'CTimesheet': EDIT_ONLY,
            'CInterviewSession': EDIT_ONLY,
            'CPayout': acl('yes', 'all', 'all', 'no'),
        },
        'permissions': {
            'assignmentPermission': 'all', 'userPermission': 'all',
            'messagePermission': 'all', 'exportPermission': 'yes',
            'massUpdatePermission': 'yes', 'userCalendarPermission': 'all',
            'mentionPermission': 'all',
        },
    }

    levels = {'Manager': 'full', 'Interview Manager': 'work', 'Coordinator': 'work',
              'Finance': 'read'}
    for name, r in roles.items():
        r['data'].update(everyday_scopes(levels[name]))
        for scope in RETIRED:
            r['data'][scope] = False
    return roles


# ------------------------------------------------------- menu and dashboards

def url_tab(tab_id, text, url, icon, scope):
    return {'type': 'url', 'id': tab_id, 'text': text, 'url': url,
            'iconClass': icon, 'color': None, 'aclScope': scope, 'onlyAdmin': False}


def group_tab(tab_id, text, icon, items):
    return {'type': 'group', 'id': tab_id, 'text': text, 'iconClass': icon,
            'color': None, 'itemList': items}


TAB_LIST = [
    'Lead', 'Contact', 'Account',
    'CDeliveryResource',
    'CProject', 'CTimesheet', 'CInterviewSession', 'Calendar',
    group_tab('bqMoney', 'Money', 'fas fa-rupee-sign', ['CPaymentBlock', 'CPayout']),
    group_tab('bqPartners', 'Partners', 'fas fa-handshake',
              ['CReferrer', 'CProvider']),
]
QUICK_CREATE = ['Lead', 'Contact', 'CTimesheet', 'CInterviewSession',
                'CPaymentBlock', 'CProject']
CALENDAR_ENTITIES = ['Meeting', 'Call', 'Task', 'CTimesheet', 'CInterviewSession']


# What each list dashlet shows per row: the name (a link) and one line of detail.
DASHLET_ROWS = {
    'CTimesheet': [['name', 'link'], ['dateStart', 'freelancer']],
    'CInterviewSession': [['name', 'link'], ['dateStart', 'paymentStatus']],
    'CPaymentBlock': [['name', 'link'], ['remainingHrs', 'paymentStatus']],
    'CPayout': [['name', 'link'], ['amount', 'payeeType']],
    'Lead': [['name', 'link'], ['bgcStatus', 'referrer']],
}


def expanded_layout(entity):
    rows = []
    for row in DASHLET_ROWS[entity]:
        if row[-1] == 'link':
            rows.append([{'name': row[0], 'link': True}])
        else:
            rows.append([{'name': n} for n in row])
    return {'rows': rows}


def records(dashlet_id, title, entity, primary, x, y, width=2, height=2,
            sort_by=None, direction='asc'):
    """Returns (layout item, options) for a Records dashlet."""
    item = {'id': dashlet_id, 'name': 'Records', 'x': x, 'y': y,
            'width': width, 'height': height}
    options = {
        'title': title, 'entityType': entity, 'primaryFilter': primary,
        'displayRecords': 8, 'autorefreshInterval': 1,
        'expandedLayout': expanded_layout(entity), 'boolFilterList': [],
    }
    if sort_by:
        options.update({'sortBy': sort_by, 'sortDirection': direction})
    return item, options


def build_dashboard():
    layout_today, layout_money, options = [], [], {}

    def add(target, pair):
        target.append(pair[0])
        options[pair[0]['id']] = pair[1]

    layout_today.append({'id': 'bqCalendar', 'name': 'Calendar', 'x': 0, 'y': 0,
                         'width': 4, 'height': 3})
    options['bqCalendar'] = {
        'title': 'My week', 'mode': 'basicWeek', 'autorefreshInterval': 1,
        'enabledScopeList': ['CTimesheet', 'CInterviewSession', 'Meeting', 'Call', 'Task'],
    }
    add(layout_today, records('bqPlannedTs', 'Planned timesheets', 'CTimesheet',
                              'planned', 0, 3, sort_by='dateStart'))
    add(layout_today, records('bqPlannedIv', 'Planned interviews', 'CInterviewSession',
                              'planned', 2, 3, sort_by='dateStart'))
    add(layout_today, records('bqLowHrs', 'Blocks with 5 or fewer hours left',
                              'CPaymentBlock', 'lowHours', 0, 5))
    add(layout_today, records('bqAwaitPay', 'Interviews waiting for payment',
                              'CInterviewSession', 'awaitingPayment', 2, 5,
                              sort_by='dateStart'))
    add(layout_today, records('bqBgc', 'BGC in verification', 'Lead',
                              'bgcInVerification', 0, 7))

    add(layout_money, records('bqUnpaidTs', 'Timesheets to pay out', 'CTimesheet',
                              'unpaid', 0, 0, sort_by='dateStart'))
    add(layout_money, records('bqUnpaidIv', 'Interviews to pay out',
                              'CInterviewSession', 'unpaid', 2, 0, sort_by='dateStart'))
    add(layout_money, records('bqDuePayouts', 'Payouts due', 'CPayout', 'due', 0, 3))
    add(layout_money, records('bqReferral', 'Referral fees to pay', 'Lead',
                              'referralDue', 2, 3))
    add(layout_money, records('bqPendingBlocks', 'Payment blocks awaiting payment',
                              'CPaymentBlock', 'pendingPayment', 0, 6))

    layout = [
        {'id': 'bqTabToday', 'name': 'Today', 'layout': layout_today},
        {'id': 'bqTabMoney', 'name': 'Money', 'layout': layout_money},
    ]
    return layout, options


# ----------------------------------------------------------------- API client

class Api:
    def __init__(self, base, user, password, api_key, dry_run):
        self.base = base.rstrip('/') + '/api/v1/'
        self.dry = dry_run
        self.headers = {'Content-Type': 'application/json'}
        if api_key:
            self.headers['X-Api-Key'] = api_key
        else:
            token = base64.b64encode(f'{user}:{password}'.encode()).decode()
            self.headers['Authorization'] = 'Basic ' + token

    def call(self, method, path, body=None, write=False):
        if write and self.dry:
            print(f'  [dry-run] {method} {path}')
            return {}
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                text = resp.read().decode()
        except urllib.error.HTTPError as e:
            detail = e.headers.get('X-Status-Reason', '')
            sys.exit(f'{method} {path} failed: HTTP {e.code} {detail}')
        except urllib.error.URLError as e:
            sys.exit(f'Cannot reach {self.base}: {e.reason}')
        return json.loads(text) if text else {}

    def get(self, path):
        return self.call('GET', path)

    def list(self, entity, select='id,name', max_size=200):
        q = urllib.parse.urlencode({'select': select, 'maxSize': max_size})
        return self.get(f'{entity}?{q}').get('list', [])


# ------------------------------------------------------------------------ run

def sync_roles(api):
    existing = {r['name']: r['id'] for r in api.list('Role')}
    ids = {}
    for name, spec in build_roles().items():
        body = {'name': name, 'data': spec['data'], 'fieldData': {}}
        body.update(spec['permissions'])
        if name in existing:
            print(f'Role "{name}": updating')
            api.call('PUT', f'Role/{existing[name]}', body, write=True)
            ids[name] = existing[name]
        else:
            print(f'Role "{name}": creating')
            res = api.call('POST', 'Role', body, write=True)
            ids[name] = res.get('id')
    return ids


def sync_settings(api):
    settings = api.get('Settings')
    currencies = settings.get('currencyList') or []
    if 'INR' not in currencies:
        currencies = currencies + ['INR']
    layout, options = build_dashboard()
    body = {
        'tabList': TAB_LIST,
        'quickCreateList': QUICK_CREATE,
        'calendarEntityList': CALENDAR_ENTITIES,
        'currencyList': currencies,
        'defaultCurrency': 'INR',
        'timeZone': 'Asia/Kolkata',
        'phoneNumberPreferredCountryList': ['in', 'us'],
        'dashboardLayout': layout,
        'dashletsOptions': options,
    }
    print('Settings: menu, quick create, calendar, currency, time zone, phone country, default dashboard')
    api.call('PUT', 'Settings', body, write=True)


def apply_dashboards(api, force):
    """Copies the default dashboard into each user's own preferences. EspoCRM shows the
    default only through this copy. Users who already built their own dashboard are left
    alone unless --reset-user-dashboards is given."""
    for user in api.list('User', 'id,userName,isActive'):
        if not user.get('isActive', True):
            continue
        prefs = api.get(f'Preferences/{user["id"]}')
        if prefs.get('dashboardLayout') and not force:
            print(f'Dashboard for {user["userName"]}: kept (personal layout)')
            continue
        print(f'Dashboard for {user["userName"]}: set to default')
        api.call('POST', 'Preferences/action/resetDashboard', {'id': user['id']}, write=True)


def assign_users(api, assignments, role_ids):
    if not assignments:
        return
    users = api.list('User', 'id,userName,emailAddress')
    ours = {i for i in role_ids.values() if i}
    for item in assignments:
        who, _, role = item.partition('=')
        if role not in role_ids:
            sys.exit(f'Unknown role "{role}". Use one of: {", ".join(role_ids)}')
        match = [u for u in users if who in (u.get('userName'), u.get('emailAddress'))]
        if not match:
            sys.exit(f'User "{who}" not found. Create the user first.')
        user = match[0]
        current = api.get(f'User/{user["id"]}')
        keep = [r for r in (current.get('rolesIds') or []) if r not in ours]
        print(f'User {user["userName"]}: role {role}')
        api.call('PUT', f'User/{user["id"]}',
                 {'rolesIds': keep + [role_ids[role]]}, write=True)


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('--url', default=os.environ.get('ESPO_URL'))
    p.add_argument('--user', default=os.environ.get('ESPO_USER'))
    p.add_argument('--password', default=os.environ.get('ESPO_PASSWORD'))
    p.add_argument('--api-key', default=os.environ.get('ESPO_API_KEY'))
    p.add_argument('--assign', action='append', default=[], metavar='USER=ROLE',
                   help='give a user (username or email) a role; repeatable')
    p.add_argument('--reset-user-dashboards', action='store_true',
                   help='replace every user\'s personal dashboard with the default')
    p.add_argument('--menu-only', action='store_true',
                   help='only update the navigation menu (Settings tabList); roles, dashboards and the rest are left alone')
    p.add_argument('--dry-run', action='store_true', help='show what would change')
    a = p.parse_args()

    if not a.url or not (a.api_key or (a.user and a.password)):
        p.error('set ESPO_URL and ESPO_USER/ESPO_PASSWORD (or ESPO_API_KEY)')

    api = Api(a.url, a.user, a.password, a.api_key, a.dry_run)
    api.get('App/user')  # fails early on bad URL or login
    if a.menu_only:
        print('Settings: navigation menu only')
        api.call('PUT', 'Settings', {'tabList': TAB_LIST}, write=True)
        print('Done.' + (' (dry run, nothing was changed)' if a.dry_run else ''))
        return
    role_ids = sync_roles(api)
    sync_settings(api)
    assign_users(api, a.assign, role_ids)
    apply_dashboards(api, a.reset_user_dashboards)
    print('Done.' + (' (dry run, nothing was changed)' if a.dry_run else ''))


if __name__ == '__main__':
    main()
