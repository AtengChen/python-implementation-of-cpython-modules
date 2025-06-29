"""This module provides various functions to manipulate time values.

There are two standard representations of time.  One is the number
of seconds since the Epoch, in UTC (a.k.a. GMT).  It may be an integer
or a floating point number (to represent fractions of seconds).
The Epoch is system-defined; on Unix, it is generally January 1st, 1970.
The actual value can be retrieved by calling gmtime(0).

The other representation is a tuple of 9 integers giving local time.
The tuple items are:
  year (including century, e.g. 1998)
  month (1-12)
  day (1-31)
  hours (0-23)
  minutes (0-59)
  seconds (0-59)
  weekday (0-6, Monday is 0)
  Julian day (day in the year, 1-366)
  DST (Daylight Savings Time) flag (-1, 0 or 1)
If the DST flag is 0, the time is given in the regular time zone;
if it is 1, the time is given in the DST time zone;
if it is -1, mktime() should guess based on the date and time.
"""

import ctypes
from ctypes import wintypes

import types
import _strptime


__all__ = ('_STRUCT_TM_ITEMS', 'altzone', 'asctime', 'ctime', 'daylight', 'get_clock_info', 'gmtime', 
           'localtime', 'mktime', 'monotonic', 'monotonic_ns', 'perf_counter', 'perf_counter_ns',
           'process_time', 'process_time_ns', 'sleep', 'strftime', 'strptime', 'struct_time', 
           'thread_time', 'thread_time_ns', 'time', 'time_ns', 'timezone', 'tzname')

_module_name = "time"
_kernel32 = ctypes.windll.kernel32


_STRUCT_TM_ITEMS = 11


class SYSTEMTIME(ctypes.Structure):
    _fields_ = [
        ("wYear", wintypes.WORD), ("wMonth", wintypes.WORD),
        ("wDayOfWeek", wintypes.WORD), ("wDay", wintypes.WORD),
        ("wHour", wintypes.WORD), ("wMinute", wintypes.WORD),
        ("wSecond", wintypes.WORD), ("wMilliseconds", wintypes.WORD),
    ]


class TIME_ZONE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("Bias", wintypes.LONG),
        ("StandardName", wintypes.WCHAR * 32),
        ("StandardDate", SYSTEMTIME),
        ("StandardBias", wintypes.LONG),
        ("DaylightName", wintypes.WCHAR * 32),
        ("DaylightDate", SYSTEMTIME),
        ("DaylightBias", wintypes.LONG),
    ]


_tzi = TIME_ZONE_INFORMATION()
_kernel32.GetTimeZoneInformation(ctypes.byref(_tzi))
altzone = (_tzi.Bias + _tzi.DaylightBias) * 60

_weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
_weekdays_full = ['Monday', 'Tuesday', 'Wednesday', 'Thursday',
                  'Friday', 'Saturday', 'Sunday']
_months   = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
             'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
_months_full = ['January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December']


def asctime(tuple=None, /) -> str:
    """asctime([tuple]) -> string

Convert a time tuple to a string, e.g. 'Sat Jun 06 16:26:11 1998'.
When the time tuple is not present, current time as returned by localtime()
is used."""
    
    if tuple is None:
        tuple = localtime()
    
    wday_str = _weekdays[tuple.tm_wday % 7]
    mon_str  = _months[tuple.tm_mon - 1]
    
    return "%s %s %2d %02d:%02d:%02d %d" % (
        wday_str, mon_str, tuple.tm_mday,
        tuple.tm_hour, tuple.tm_min, tuple.tm_sec,
        tuple.tm_year
    )


def ctime(seconds=None, /) -> str:
    """ctime(seconds) -> string

Convert a time in seconds since the Epoch to a string in local time.
This is equivalent to asctime(localtime(seconds)). When the time tuple is
not present, current time as returned by localtime() is used."""
    
    return asctime(localtime(seconds))


_dd = _tzi.DaylightDate
daylight = int(any([_dd.wMonth, _dd.wDay, _dd.wDayOfWeek, _dd.wHour,
                    _dd.wMinute, _dd.wSecond, _dd.wMilliseconds]))


def get_clock_info(name):
    """get_clock_info(name: str) -> dict

Get information of the specified clock."""

    name = name.lower()
    if name in ('monotonic', 'perf_counter'):
        return types.SimpleNamespace(
            resolution=1 / _frequency,
            adjustable=False,
            implementation="QueryPerformanceCounter",
            monotonic=True
        )

    elif name == 'process_time':
        return types.SimpleNamespace(
            resolution=1e-7,
            adjustable=False,
            implementation="GetProcessTimes",
            monotonic=True
        )

    elif name == 'thread_time':
        return types.SimpleNamespace(
            resolution=1e-7,
            adjustable=False,
            implementation="GetThreadTimes",
            monotonic=True
        )

    elif name == 'time':
        return types.SimpleNamespace(
            resolution=1e-7,
            adjustable=True,
            implementation="GetSystemTimeAsFileTime",
            monotonic=False
        )

    else:
        raise ValueError(f"unknown clock: {name}")


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_ulong),
                ("dwHighDateTime", ctypes.c_ulong)]


def _calc_weekday(year, month, day):
    t = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4]
    y = year - (month < 3)
    w = (y + y//4 - y//100 + y//400 + t[month-1] + day) % 7
    return (w - 1) % 7


def _is_leap(year):
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)


_month_days = [31,28,31,30,31,30,31,31,30,31,30,31]


def _calc_yday(year, month, day):
    mdays = _month_days.copy()
    if _is_leap(year):
        mdays[1] = 29
    return day + sum(mdays[:month-1])


def gmtime(seconds=None, /) -> tuple:
    """gmtime([seconds]) -> (tm_year, tm_mon, tm_mday, tm_hour, tm_min,
                       tm_sec, tm_wday, tm_yday, tm_isdst)

Convert seconds since the Epoch to a time tuple expressing UTC (a.k.a.
GMT).  When 'seconds' is not passed in, convert the current time instead.

If the platform supports the tm_gmtoff and tm_zone, they are available as
attributes only."""
    
    if seconds is None:
        seconds = time()
    
    return localtime(seconds)


_EPOCH_DIFF = 11644473600


def localtime(seconds=None, /) -> tuple:
    """localtime([seconds]) -> (tm_year,tm_mon,tm_mday,tm_hour,tm_min,
                          tm_sec,tm_wday,tm_yday,tm_isdst)

Convert seconds since the Epoch to a time tuple expressing local time.
When 'seconds' is not passed in, convert the current time instead."""

    mdays = _month_days.copy()
    if seconds is not None:
        second = seconds % 60
        seconds //= 60
        minute = seconds % 60
        seconds //= 60
        hour = seconds % 24
        days = seconds // 24
    
        year = 1970
        while 1:
            is_leap = _is_leap(year)
            year_days = 366 if is_leap else 365
            if days >= year_days:
                days -= year_days
                year += 1
            else:
                break
    
        if _is_leap(year):
            mdays[1] = 29
        month = 1
        for mlen in mdays:
            if days + 1 > mlen:
                days -= mlen
                month += 1
            else:
                break
        day = days + 1

    else:
        st = SYSTEMTIME()
    
        _kernel32.GetLocalTime(ctypes.byref(st))
    
        year, month, day = st.wYear, st.wMonth, st.wDay

        if day == 0:
            month -= 1
            if month == 0:
                month = 12
                year -= 1
                
            if _is_leap(year):
                mdays[1] = 29
            day = mdays[month-1]

        hour, minute, second = st.wHour, st.wMinute, st.wSecond
    
    tm_wday = _calc_weekday(year, month, day)
    tm_yday = _calc_yday(year, month, day)
    tm_isdst = 0

    return struct_time((
        year, month, int(day),
        int(hour), int(minute), int(second),
        int(tm_wday), int(tm_yday), int(tm_isdst)
    ))


def mktime(tuple, /) -> float:
    """mktime(tuple) -> floating point number

Convert a time tuple in local time to seconds since the Epoch.
Note that mktime(gmtime(0)) will not generally return zero for most
time zones; instead the returned value will either be equal to that
of the timezone or altzone attributes on the time module."""
    
    year, mon, mday = tuple.tm_year, tuple.tm_mon, tuple.tm_mday
    hour, minute, sec = tuple.tm_hour, tuple.tm_min, tuple.tm_sec

    days = 0
    for y in range(1970, year):
        days += 366 if _is_leap(y) else 365

    mdays = _month_days.copy()
    if _is_leap(year):
        mdays[1] = 29
    
    days += sum(mdays[:mon-1])

    days += (mday - 1)
    local_secs = days * 86400 + hour * 3600 + minute * 60 + sec

    offset_sec = _get_local_utc_offset_seconds(tuple.tm_isdst)
    return local_secs + offset_sec


_freq = ctypes.c_longlong()
if not _kernel32.QueryPerformanceFrequency(ctypes.byref(_freq)):
    raise OSError("QueryPerformanceFrequency failed")

_frequency = _freq.value


def monotonic() -> float:
    """monotonic() -> float

Monotonic clock, cannot go backward."""

    counter = ctypes.c_longlong()
    if not _kernel32.QueryPerformanceCounter(ctypes.byref(counter)):
        raise OSError("QueryPerformanceCounter failed")
    return counter.value / _frequency


def monotonic_ns() -> int:
    """monotonic_ns() -> int

Monotonic clock, cannot go backward, as nanoseconds."""

    return int(monotonic() * 1_000_000_000)


perf_counter = monotonic

perf_counter_ns = monotonic_ns


def _filetime_to_seconds(ft):
    high = ft.dwHighDateTime
    low  = ft.dwLowDateTime
    ticks = (high << 32) | low
    return ticks / 10_000_000


_kernel32.GetCurrentProcess.restype = wintypes.HANDLE
_kernel32.GetProcessTimes.argtypes = (
    wintypes.HANDLE,      # hProcess
    ctypes.POINTER(FILETIME),  # lpCreationTime
    ctypes.POINTER(FILETIME),  # lpExitTime
    ctypes.POINTER(FILETIME),  # lpKernelTime
    ctypes.POINTER(FILETIME),  # lpUserTime
)
_kernel32.GetProcessTimes.restype = wintypes.BOOL


def _get_user_cpu_time(current, times):
    hProc = getattr(_kernel32, current)()
    
    creation = FILETIME()
    exit     = FILETIME()
    kernel   = FILETIME()
    user     = FILETIME()

    ok = getattr(_kernel32, times)(
        hProc,
        ctypes.byref(creation),
        ctypes.byref(exit),
        ctypes.byref(kernel),
        ctypes.byref(user)
    )
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    
    return _filetime_to_seconds(kernel) + _filetime_to_seconds(user)


def process_time() -> float:
    """process_time() -> float

Process time for profiling: sum of the kernel and user-space CPU time."""
    
    return _get_user_cpu_time("GetCurrentProcess", "GetProcessTimes")


def process_time_ns() -> int:
    """process_time() -> int

Process time for profiling as nanoseconds:
sum of the kernel and user-space CPU time."""

    return int(process_time() * 1_000_000_000)


CREATE_WAITABLE_TIMER_HIGH_RESOLUTION = 0x00000002
SYNCHRONIZE               = 0x00100000
TIMER_MODIFY_STATE        = 0x0002
DESIRED_ACCESS            = SYNCHRONIZE | TIMER_MODIFY_STATE
INFINITE                  = 0xFFFFFFFF
NULL                      = ctypes.c_void_p(0)


class LARGE_INTEGER(ctypes.Union):
    class _S(ctypes.Structure):
        _fields_ = [
            ("LowPart",  wintypes.DWORD),
            ("HighPart", wintypes.LONG),
        ]
    _fields_ = [
        ("u", _S),
        ("QuadPart", ctypes.c_longlong),
    ]
   
_kernel32.CreateWaitableTimerExW.argtypes = (
    ctypes.c_void_p,  # lpTimerAttributes
    wintypes.LPCWSTR, # lpTimerName
    wintypes.DWORD,   # dwFlags
    wintypes.DWORD,   # dwDesiredAccess
)
_kernel32.CreateWaitableTimerExW.restype = wintypes.HANDLE

_kernel32.SetWaitableTimer.argtypes = (
    wintypes.HANDLE,
    ctypes.POINTER(LARGE_INTEGER),
    wintypes.LONG,
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.BOOL,
)

_kernel32.SetWaitableTimer.restype = wintypes.BOOL

_kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
_kernel32.WaitForSingleObject.restype = wintypes.DWORD

_kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
_kernel32.CloseHandle.restype  = wintypes.BOOL

hTimer = _kernel32.CreateWaitableTimerExW(
    None,
    None,
    CREATE_WAITABLE_TIMER_HIGH_RESOLUTION,
    DESIRED_ACCESS
)

if not hTimer:
    raise ctypes.WinError(ctypes.get_last_error())


def sleep(seconds, /):
    """sleep(seconds)

Delay execution for a given number of seconds.  The argument may be
a floating point number for subsecond precision."""

    if seconds == 0:
        _kernel32.Sleep(0)
        return
    
    li = LARGE_INTEGER()
    li.QuadPart = -int(seconds * 10_000_000)

    if not _kernel32.SetWaitableTimer(hTimer, ctypes.byref(li), 0, None, None, False):
        raise ctypes.WinError(ctypes.get_last_error())
    
    ret = _kernel32.WaitForSingleObject(hTimer, INFINITE)
    if ret != 0:  # WAIT_OBJECT_0 == 0
        raise ctypes.WinError(ctypes.get_last_error())


def _zero(n, width=2):
    return str(n).zfill(width)


def _yday(tm):
    return str(tm.tm_yday).zfill(3)


_strtime_handlers = {
    'Y': lambda tm: str(tm.tm_year),
    'y': lambda tm: _zero(tm.tm_year % 100),
    'm': lambda tm: _zero(tm.tm_mon),
    'd': lambda tm: _zero(tm.tm_mday),
    'H': lambda tm: _zero(tm.tm_hour),
    'M': lambda tm: _zero(tm.tm_min),
    'S': lambda tm: _zero(tm.tm_sec),
    'a': lambda tm: _weekdays[tm.tm_wday],
    'A': lambda tm: _weekdays_full[tm.tm_wday],
    'b': lambda tm: _months[tm.tm_mon - 1],
    'B': lambda tm: _months_full[tm.tm_mon - 1],
    'w': lambda tm: str(tm.tm_wday),       # 0=Mon ¡­ 6=Sun
    'j': lambda tm: _yday(tm),              # day of year
    '%': lambda tm: '%',
    }


def strftime(format, tuple=None, /) -> str:
    """strftime(format[, tuple]) -> string

Convert a time tuple to a string according to a format specification.
See the library reference manual for formatting codes. When the time tuple
is not present, current time as returned by localtime() is used.

Commonly used format codes:

%Y  Year with century as a decimal number.
%m  Month as a decimal number [01,12].
%d  Day of the month as a decimal number [01,31].
%H  Hour (24-hour clock) as a decimal number [00,23].
%M  Minute as a decimal number [00,59].
%S  Second as a decimal number [00,61].
%z  Time zone offset from UTC.
%a  Locale's abbreviated weekday name.
%A  Locale's full weekday name.
%b  Locale's abbreviated month name.
%B  Locale's full month name.
%c  Locale's appropriate date and time representation.
%I  Hour (12-hour clock) as a decimal number [01,12].
%p  Locale's equivalent of either AM or PM.

Other codes may be available on your platform.  See documentation for
the C library strftime function.
"""
    res = []
    i = 0
    L = len(format)
    while i < L:
        if format[i] == '%' and i+1 < L:
            code = format[i+1]
            fn = _strtime_handlers.get(code)
            if fn:
                res.append(fn(tuple))
            else:
                res.append('%' + code)
            i += 2
        else:
            res.append(format[i])
            i += 1

    return ''.join(res)


_strptime.time = __import__(__name__)
strptime = _strptime._strptime


class struct_time(tuple):
    """The time value as returned by gmtime(), localtime(), and strptime(), and
 accepted by asctime(), mktime() and strftime().  May be considered as a
 sequence of 9 integers.

 Note that several fields' values are not the same as those defined by
 the C language standard for struct tm.  For example, the value of the
 field tm_year is the actual year, not year - 1900.  See individual
 fields' descriptions for details."""
    
    __match_args__ = ('tm_year', 'tm_mon', 'tm_mday', 'tm_hour', 'tm_min', 
                      'tm_sec', 'tm_wday', 'tm_yday', 'tm_isdst')

    def __new__(cls, *args, **kwargs):
        inst = super().__new__(cls)
        inst.tm_year, inst.tm_mon, inst.tm_mday, inst.tm_hour, inst.tm_min, \
            inst.tm_sec, inst.tm_wday, inst.tm_yday, inst.tm_isdst = args[0]
        
        return inst

    def __reduce__(self):
        return (struct_time, (self.tm_year, self.tm_mon, self.tm_mday,
                   self.tm_hour, self.tm_min, self.tm_sec,
                   self.tm_wday, self.tm_yday, self.tm_isdst),
                   {'tm_zone': None, 'tm_gmtoff': None}
               )
    
    def __repr__(self):
        return f"{_module_name}.struct_time(tm_year={self.tm_year}, tm_mon={self.tm_mon}, " \
               f"tm_mday={self.tm_mday}, tm_hour={self.tm_hour}, tm_min={self.tm_min}, " \
               f"tm_sec={self.tm_sec}, tm_wday={self.tm_wday}, tm_yday={self.tm_yday}, tm_isdst={self.tm_isdst})"


def thread_time() -> float:
    """thread_time() -> float

Thread time for profiling: sum of the kernel and user-space CPU time."""
    
    return _get_user_cpu_time("GetCurrentThread", "GetThreadTimes")


def thread_time_ns() -> int:
    """thread_time() -> int

Thread time for profiling as nanoseconds:
sum of the kernel and user-space CPU time."""

    return int(thread_time() * 1_000_000_000)


def time() -> float:
    """time() -> floating point number

Return the current time in seconds since the Epoch.
Fractions of a second may be present if the system clock provides them."""
    
    ft = FILETIME()
    _kernel32.GetSystemTimeAsFileTime(ctypes.byref(ft))
    return _filetime_to_seconds(ft) - _EPOCH_DIFF


def time_ns() -> int:
    """time_ns() -> int

Return the current time in nanoseconds since the Epoch."""
    
    return int(time() * 1_000_000_000)


def _get_local_utc_offset_seconds(isdst_flag):
    _kernel32.GetTimeZoneInformation(ctypes.byref(_tzi))
    bias = _tzi.Bias
    if isdst_flag > 0:
        bias += _tzi.DaylightBias

    return bias * 60


timezone = _get_local_utc_offset_seconds(0)


class DYNAMIC_TIME_ZONE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("Bias", wintypes.LONG),
        ("StandardName", wintypes.WCHAR * 32),
        ("StandardDate", SYSTEMTIME),
        ("StandardBias", wintypes.LONG),
        ("DaylightName", wintypes.WCHAR * 32),
        ("DaylightDate", SYSTEMTIME),
        ("DaylightBias", wintypes.LONG),
        ("TimeZoneKeyName", wintypes.WCHAR * 128),
        ("DynamicDaylightTimeDisabled", wintypes.BOOL),
    ]
    
_kernel32.GetDynamicTimeZoneInformation.argtypes = [
    ctypes.POINTER(DYNAMIC_TIME_ZONE_INFORMATION)
]
_kernel32.GetDynamicTimeZoneInformation.restype = wintypes.DWORD

info = DYNAMIC_TIME_ZONE_INFORMATION()
result = _kernel32.GetDynamicTimeZoneInformation(ctypes.byref(info))
if result == INFINITE:
    raise ctypes.WinError(ctypes.get_last_error())

std = info.StandardName
dst = info.DaylightName
tzname = std, dst

# import sys
# sys.modules["time"] = __import__(__name__)
