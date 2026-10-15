#!/usr/bin/env python3
"""Sets up Benchteq spec v2 settings in EspoCRM through the REST API.

Creates or updates (safe to run again, it never creates duplicates):
  - the four roles: Manager, Interview Manager, Coordinator, Finance
  - the menu, quick-create list, Calendar entity list, INR currency, India time zone
    and India/US as the first phone-number countries
  - a dashboard per role

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
                   'CInterviewSession', 'CPayout', 'CReferrer', 'CProvider', 'CBgcCheck']
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
            'CPayout': False, 'CBgcCheck': False,
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
            'CBgcCheck': WORK_DEL,
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
            'CInterviewSession': EDIT_ONLY, 'CBgcCheck': EDIT_ONLY,
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
    'CProject', 'CTimesheet', 'CInterviewSession', 'CBgcCheck', 'Calendar',
    group_tab('bqMoney', 'Money', 'fas fa-rupee-sign', ['CPaymentBlock', 'CPayout']),
    group_tab('bqPartners', 'Partners', 'fas fa-handshake',
              ['CReferrer', 'CProvider']),
]
QUICK_CREATE = ['Lead', 'Contact', 'CTimesheet', 'CInterviewSession', 'CBgcCheck',
                'CPaymentBlock', 'CProject']
CALENDAR_ENTITIES = ['Meeting', 'Call', 'Task', 'CTimesheet', 'CInterviewSession']


# What each list dashlet shows per row: the name (a link) and one line of detail.
DASHLET_ROWS = {
    'CTimesheet': [['name', 'link'], ['dateStart', 'freelancer']],
    'CInterviewSession': [['name', 'link'], ['dateStart', 'paymentStatus']],
    'CPaymentBlock': [['name', 'link'], ['remainingHrs', 'paymentStatus']],
    'CPayout': [['name', 'link'], ['amount', 'payeeType']],
    'Lead': [['name', 'link'], ['bgcStatus', 'referrer']],
    'CBgcCheck': [['name', 'link'], ['bgcType', 'bgcStatus']],
    'Task': [['name', 'link'], ['dateEnd', 'priority']],
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
            sort_by=None, direction='asc', only_my=False):
    """Returns (layout item, options) for a Records dashlet."""
    item = {'id': dashlet_id, 'name': 'Records', 'x': x, 'y': y,
            'width': width, 'height': height}
    options = {
        'title': title, 'entityType': entity, 'primaryFilter': primary,
        'displayRecords': 8, 'autorefreshInterval': 1,
        'expandedLayout': expanded_layout(entity),
        'boolFilterList': ['onlyMy'] if only_my else [],
    }
    if sort_by:
        options.update({'sortBy': sort_by, 'sortDirection': direction})
    return item, options


def calendar(dashlet_id, title, scopes):
    item = {'id': dashlet_id, 'name': 'Calendar', 'x': 0, 'y': 0, 'width': 4, 'height': 3}
    return item, {'title': title, 'mode': 'basicWeek', 'autorefreshInterval': 1,
                  'enabledScopeList': scopes}


# Each dashboard is a list of tabs. A tab is (name, [dashlets]); a dashlet is
# (kind, id, title, entity, filter, extra). Positions are filled in below: two per row.
W = [
    ('cal', 'bqCalendar', 'My week', ['CTimesheet', 'CInterviewSession', 'Meeting', 'Call', 'Task']),
    ('cal', 'bqCalendarIv', 'My week', ['CInterviewSession', 'Meeting', 'Call', 'Task']),
]
CAL_ALL, CAL_IV = W

PLANNED_TS = ('rec', 'bqPlannedTs', 'Planned timesheets', 'CTimesheet', 'planned',
              {'sort_by': 'dateStart'})
PLANNED_IV = ('rec', 'bqPlannedIv', 'Planned interviews', 'CInterviewSession', 'planned',
              {'sort_by': 'dateStart'})
NO_FREELANCER = ('rec', 'bqNoFreelancer', 'Interviews with no freelancer',
                 'CInterviewSession', 'noFreelancer', {'sort_by': 'dateStart'})
AWAIT_PAY = ('rec', 'bqAwaitPay', 'Interviews waiting for payment', 'CInterviewSession',
             'awaitingPayment', {'sort_by': 'dateStart'})
LOW_HRS = ('rec', 'bqLowHrs', 'Packages with 5 or fewer hours left', 'CPaymentBlock',
           'lowHours', {})
MY_OVERDUE = ('rec', 'bqMyOverdue', 'My overdue tasks', 'Task', 'overdue',
              {'only_my': True, 'sort_by': 'dateEnd'})
MY_TODAY = ('rec', 'bqMyToday', 'My tasks due today', 'Task', 'today', {'only_my': True})
BGC_CHECK = ('rec', 'bqBgcCheck', 'BGC checks in verification', 'CBgcCheck',
             'inVerification', {})
BGC_LEAD = ('rec', 'bqBgc', 'New-lead BGC in verification', 'Lead', 'bgcInVerification', {})
UNPAID_TS = ('rec', 'bqUnpaidTs', 'Timesheets to pay out', 'CTimesheet', 'unpaid',
             {'sort_by': 'dateStart'})
UNPAID_IV = ('rec', 'bqUnpaidIv', 'Interviews to pay out', 'CInterviewSession', 'unpaid',
             {'sort_by': 'dateStart'})
DUE_PAYOUTS = ('rec', 'bqDuePayouts', 'Payouts due', 'CPayout', 'due', {})
REF_LEAD = ('rec', 'bqReferral', 'Referral fees to pay (leads)', 'Lead', 'referralDue', {})
REF_BGC = ('rec', 'bqReferralBgc', 'Referral fees to pay (BGC)', 'CBgcCheck',
           'referralDue', {})
PENDING_PKG = ('rec', 'bqPendingBlocks', 'Packages awaiting payment', 'CPaymentBlock',
               'pendingPayment', {})

# Who sees what. Manager first: anyone with the Manager role gets the full set.
DASHBOARDS = {
    'Manager': [
        ('Today', [CAL_ALL, PLANNED_IV, PLANNED_TS, MY_OVERDUE, MY_TODAY]),
        ('Attention', [NO_FREELANCER, LOW_HRS, AWAIT_PAY, BGC_CHECK, BGC_LEAD]),
        ('Money', [UNPAID_TS, UNPAID_IV, DUE_PAYOUTS, REF_LEAD, REF_BGC, PENDING_PKG]),
    ],
    'Interview Manager': [
        ('Interviews', [CAL_IV, PLANNED_IV, NO_FREELANCER, AWAIT_PAY, MY_OVERDUE,
                        MY_TODAY]),
    ],
    'Coordinator': [
        ('Today', [CAL_ALL, PLANNED_IV, PLANNED_TS, MY_OVERDUE, MY_TODAY]),
        ('Follow up', [NO_FREELANCER, LOW_HRS, BGC_CHECK, BGC_LEAD]),
    ],
    'Finance': [
        ('Money', [UNPAID_TS, UNPAID_IV, DUE_PAYOUTS, REF_LEAD, REF_BGC, PENDING_PKG]),
    ],
}
ROLE_ORDER = ['Manager', 'Interview Manager', 'Coordinator', 'Finance']


def build_dashboard(role='Manager'):
    layout, options = [], {}
    for tab_name, dashlets in DASHBOARDS[role]:
        tab, y, col = [], 0, 0
        for d in dashlets:
            if d[0] == 'cal':
                pair = calendar(d[1], d[2], d[3])
                y, col = 3, 0
            else:
                extra = d[5]
                pair = records(d[1], d[2], d[3], d[4], col * 2, y, **extra)
                col += 1
                if col == 2:
                    col, y = 0, y + 2
            tab.append(pair[0])
            options[pair[0]['id']] = pair[1]
        tab_id = 'bqTab' + ''.join(c for c in tab_name.title() if c.isalnum())
        layout.append({'id': tab_id, 'name': tab_name, 'layout': tab})
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
    layout, options = build_dashboard('Manager')
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
    """Gives each user the dashboard that fits their role. A user with several roles gets
    the first match in ROLE_ORDER. Users who already built their own dashboard are left
    alone unless --reset-user-dashboards is given."""
    for user in api.list('User', 'id,userName,isActive'):
        if not user.get('isActive', True):
            continue
        prefs = api.get(f'Preferences/{user["id"]}')
        if prefs.get('dashboardLayout') and not force:
            print(f'Dashboard for {user["userName"]}: kept (personal layout)')
            continue
        names = set((api.get(f'User/{user["id"]}').get('rolesNames') or {}).values())
        role = next((r for r in ROLE_ORDER if r in names), 'Manager')
        layout, options = build_dashboard(role)
        print(f'Dashboard for {user["userName"]}: {role}')
        api.call('PUT', f'Preferences/{user["id"]}',
                 {'dashboardLayout': layout, 'dashletsOptions': options}, write=True)


def assign_users(api, assignments, role_ids):
    """A user can get several of our roles: repeat --assign for the same user."""
    if not assignments:
        return
    users = api.list('User', 'id,userName,emailAddress')
    ours = {i for i in role_ids.values() if i}
    wanted = {}
    for item in assignments:
        who, _, role = item.partition('=')
        if role not in role_ids:
            sys.exit(f'Unknown role "{role}". Use one of: {", ".join(role_ids)}')
        match = [u for u in users if who in (u.get('userName'), u.get('emailAddress'))]
        if not match:
            sys.exit(f'User "{who}" not found. Create the user first.')
        user = match[0]
        wanted.setdefault(user['id'], (user, []))[1].append(role)
    for user, roles in wanted.values():
        current = api.get(f'User/{user["id"]}')
        keep = [r for r in (current.get('rolesIds') or []) if r not in ours]
        print(f'User {user["userName"]}: role {", ".join(roles)}')
        api.call('PUT', f'User/{user["id"]}',
                 {'rolesIds': keep + [role_ids[r] for r in roles]}, write=True)


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
        print('Settings: navigation menu and currency list (INR and USD)')
        currencies = api.get('Settings').get('currencyList') or []
        for code in ('INR', 'USD'):
            if code not in currencies:
                currencies = currencies + [code]
        api.call('PUT', 'Settings', {'tabList': TAB_LIST, 'currencyList': currencies}, write=True)
        print('Done.' + (' (dry run, nothing was changed)' if a.dry_run else ''))
        return
    role_ids = sync_roles(api)
    sync_settings(api)
    assign_users(api, a.assign, role_ids)
    apply_dashboards(api, a.reset_user_dashboards)
    print('Done.' + (' (dry run, nothing was changed)' if a.dry_run else ''))


if __name__ == '__main__':
    main()
