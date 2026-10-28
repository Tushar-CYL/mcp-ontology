"""Fetch a time slice of alibaba/cluster-trace-microservices-v2022.

Index math is ported from the upstream fetchData.sh. The release is split by
*minutes of elapsed trace time*, with a different chunk size per table:

    CallGraph        3 min/file     ~213 MiB/file   (~4.2 GiB per trace-hour)
    MSMetricsUpdate  30 min/file    ~355 MiB/file
    NodeMetricsUpdate 720 min/file  ~634 MiB/file
    MCRRTUpdate      3 min/file     ~166 MiB/file

The 3-minute granularity of CallGraph is what makes this project fit on a
small machine: scale is dialled in 3-minute steps, not hours.

Downloads resume via HTTP Range, so an interrupted fetch costs nothing.
Nothing is decompressed here - the parser streams each archive and the
raw file is deleted immediately after. See ingest/parse_callgraph.py.

Usage:
    python ingest/fetch.py --start 0d0 --end 0d1              # one trace-hour
    python ingest/fetch.py --start 0d0 --minutes 9            # smoke slice
    python ingest/fetch.py --start 0d0 --minutes 9 --only CallGraph
    python ingest/fetch.py --start 0d0 --end 0d1 --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

BASE = "https://aliopentrace.oss-cn-beijing.aliyuncs.com/v2022MicroservicesTraces"


@dataclass(frozen=True)
class Table:
    name: str          # local directory name
    remote: str        # remote directory + file stem
    minutes: int       # trace-minutes covered by one file


TABLES = (
    Table("CallGraph", "CallGraph/CallGraph", 3),
    Table("MSMetrics", "MSMetricsUpdate/MSMetricsUpdate", 30),
    Table("NodeMetrics", "NodeMetricsUpdate/NodeMetricsUpdate", 720),
    Table("MSRTMCR", "MCRRTUpdate/MCRRTUpdate", 3),
)

_DAYHOUR = re.compile(r"^(\d+)d(\d+)$")


def parse_daytime(s: str) -> int:
    """'0d1' -> elapsed minutes from trace start."""
    m = _DAYHOUR.match(s)
    if not m:
        raise argparse.ArgumentTypeError(f"expected <day>d<hour>, got {s!r}")
    day, hour = int(m.group(1)), int(m.group(2))
    return day * 24 * 60 + hour * 60


def indices(tbl: Table, start_min: int, end_min: int) -> list[int]:
    """File indices covering [start_min, end_min).

    Mirrors fetchData.sh, including its special case: a table whose chunk is
    coarser than the requested window still needs the partially-covered
    trailing file, or the window ends up with no rows at all.
    """
    if end_min <= start_min:
        return []
    start_idx = start_min // tbl.minutes
    end_idx = end_min // tbl.minutes - 1
    if end_min % tbl.minutes != 0:
        end_idx += 1
    return list(range(start_idx, max(start_idx, end_idx) + 1))


def human(n: int) -> str:
    f = float(n)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if f < 1024 or unit == "GiB":
            return f"{f:,.1f} {unit}"
        f /= 1024
    return f"{f:,.1f} GiB"


def remote_size(client: httpx.Client, url: str) -> tuple[int | None, str | None]:
    """Size of the remote file, plus WHY if we could not get it.

    Returns (size, None) on success, (None, reason) on failure. An earlier
    version swallowed the exception entirely and printed "HEAD failed",
    which told a user nothing about whether it was DNS, TLS, a proxy or a
    403 - so nobody could act on it.

    Falls back to a one-byte ranged GET, because plenty of corporate
    proxies forward GET happily while blocking HEAD outright. A failed HEAD
    is not a reason to give up on the file.
    """
    why = []
    try:
        r = client.head(url, timeout=45.0, follow_redirects=True)
        if r.status_code == 200:
            n = int(r.headers.get("content-length", 0))
            if n:
                return n, None
        why.append(f"HEAD -> HTTP {r.status_code}")
    except httpx.HTTPError as e:
        why.append(f"HEAD -> {type(e).__name__}: {e}")

    try:
        r = client.get(url, headers={"Range": "bytes=0-0"}, timeout=45.0,
                       follow_redirects=True)
        if r.status_code == 206:
            cr = r.headers.get("content-range", "")
            if "/" in cr:
                return int(cr.rsplit("/", 1)[1]), None
        if r.status_code == 200:
            n = int(r.headers.get("content-length", 0))
            if n:
                return n, None
        why.append(f"ranged GET -> HTTP {r.status_code}")
    except httpx.HTTPError as e:
        why.append(f"ranged GET -> {type(e).__name__}: {e}")

    return None, "; ".join(why)


def download(client: httpx.Client, url: str, dest: Path, retries: int = 5) -> bool:
    """Resumable download. Returns True if the file is complete on disk."""
    total, why = remote_size(client, url)
    if total is None:
        print(f"    ! cannot reach {dest.name}", file=sys.stderr)
        print(f"      {why}", file=sys.stderr)
        return False

    if dest.exists() and dest.stat().st_size == total:
        print(f"    = {dest.name} already complete ({human(total)})")
        return True

    for attempt in range(1, retries + 1):
        have = dest.stat().st_size if dest.exists() else 0
        if have == total:
            return True
        if have > total:                      # corrupt/partial from an older run
            dest.unlink()
            have = 0

        headers = {"Range": f"bytes={have}-"} if have else {}
        mode = "ab" if have else "wb"
        started, last = time.monotonic(), have
        try:
            with client.stream("GET", url, headers=headers, timeout=120.0,
                               follow_redirects=True) as r:
                if r.status_code not in (200, 206):
                    raise httpx.HTTPError(f"status {r.status_code}")
                with dest.open(mode) as fh:
                    for chunk in r.iter_bytes(1 << 20):
                        fh.write(chunk)
                        last += len(chunk)
                        if last % (64 << 20) < (1 << 20):
                            el = max(time.monotonic() - started, 1e-6)
                            rate = (last - have) / el / 1048576
                            pct = 100.0 * last / total
                            print(f"      {dest.name}: {pct:5.1f}%  "
                                  f"{human(last)}/{human(total)}  {rate:.1f} MiB/s")
        except (httpx.HTTPError, OSError) as e:
            print(f"    ~ {dest.name} attempt {attempt}/{retries} interrupted: {e}",
                  file=sys.stderr)
            time.sleep(min(2 ** attempt, 30))
            continue

        if dest.exists() and dest.stat().st_size == total:
            el = max(time.monotonic() - started, 1e-6)
            print(f"    + {dest.name} {human(total)} in {el:,.0f}s")
            return True

    print(f"    ! {dest.name} FAILED after {retries} attempts", file=sys.stderr)
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", type=parse_daytime, default=0,
                    help="slice start as <day>d<hour>, e.g. 0d0")
    ap.add_argument("--end", type=parse_daytime,
                    help="slice end as <day>d<hour>, exclusive")
    ap.add_argument("--minutes", type=int,
                    help="slice length in trace-minutes (alternative to --end)")
    ap.add_argument("--only", action="append", choices=[t.name for t in TABLES],
                    help="restrict to one or more tables (repeatable)")
    ap.add_argument("--dest", type=Path, default=Path("data/raw"))
    ap.add_argument("--insecure", action="store_true",
                    help="skip TLS verification; for corporate TLS "
                         "interception only")
    ap.add_argument("--dry-run", action="store_true",
                    help="list files and total bytes without downloading")
    args = ap.parse_args()

    if args.end is None and args.minutes is None:
        ap.error("give --end or --minutes")
    end_min = args.end if args.end is not None else args.start + args.minutes
    if end_min <= args.start:
        ap.error("slice end must be after start")

    wanted = [t for t in TABLES if not args.only or t.name in args.only]
    span = end_min - args.start
    print(f"slice: minute {args.start} -> {end_min}  ({span} trace-minutes)")

    plan: list[tuple[Table, int, str, Path]] = []
    for t in wanted:
        for idx in indices(t, args.start, end_min):
            url = f"{BASE}/{t.remote}_{idx}.tar.gz"
            plan.append((t, idx, url, args.dest / t.name / f"{t.name}_{idx}.tar.gz"))

    headers = {"User-Agent": "okg-ingest/0.1 (+research; resumable)"}
    # trust_env is on by default, so HTTP_PROXY / HTTPS_PROXY are honoured
    # without any extra work. --insecure exists only for corporate TLS
    # interception, where the proxy presents its own certificate.
    with httpx.Client(headers=headers, http2=False,
                      verify=not args.insecure) as client:
        if args.dry_run:
            total = 0
            for t, idx, url, dest in plan:
                sz, why = remote_size(client, url)
                total += sz or 0
                print(f"  {t.name:<12} idx {idx:<5} "
                      f"{human(sz) if sz else 'UNAVAILABLE':>12}"
                      f"   {'(on disk)' if dest.exists() else ''}")
                if sz is None:
                    print(f"               {why}")
            print(f"\n{len(plan)} files, {human(total)} total")
            return 0

        ok = failed = 0
        for t, idx, url, dest in plan:
            dest.parent.mkdir(parents=True, exist_ok=True)
            print(f"  {t.name} idx {idx}")
            if download(client, url, dest):
                ok += 1
            else:
                failed += 1

    print(f"\ndone: {ok} complete, {failed} failed")

    # Nothing at all got through: that is a network policy problem, not a
    # flaky transfer, and retrying will not help. Say so, and say what will.
    if failed and not ok:
        print(f"""
NOTHING downloaded. The reason is printed above each file - read it, it
says which of these you are hitting:

  "ConnectError" / "getaddrinfo failed"
      DNS or egress is blocked. You are probably behind a proxy. Set it:
          $env:HTTPS_PROXY = "http://user:pass@proxy.company.com:8080"
          $env:HTTP_PROXY  = $env:HTTPS_PROXY
      then run setup again.

  "SSLError" / "CERTIFICATE_VERIFY_FAILED"
      Your company inspects TLS with its own certificate. Either point
      Python at the company CA bundle:
          $env:SSL_CERT_FILE = "C:\\path\\to\\company-ca.pem"
      or, if you accept the risk on a corporate network:
          python ingest\\fetch.py --start 0d0 --minutes 9 --insecure

  "HTTP 403" / "HTTP 404"
      The host is reachable but refusing. A web filter is likely blocking
      the domain {BASE.split('/')[2]}.

If none of that is available to you, you do not need to download anything:
copy the `data\\raw` folder from a machine that already has it, put it in
this project, and run setup again. It will find the archives and skip this
step entirely.""", file=sys.stderr)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
