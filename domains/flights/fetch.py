"""Download the flights data. Two sources, both free, neither needs a login.

  OpenFlights  airports / airlines / routes - the static network.
               ~3.8 MB total, from the project's GitHub snapshot.

  BTS          On-Time Reporting Carrier Performance - every commercial
               flight in US airspace, one ZIP per month, ~27 MB each.
               This is what gives the graph dates, delays and cancellations.

Resumable via HTTP Range, and TLS is verified against the OS trust store so
it works behind a corporate proxy that re-signs HTTPS. Both behaviours are
lifted from the other domain's fetcher, where they were earned the hard way.

Usage:
    python domains/flights/fetch.py                     routes + Jan 2025
    python domains/flights/fetch.py --months 2025-01 2025-02
    python domains/flights/fetch.py --dry-run
"""

from __future__ import annotations

import argparse
import re
import ssl
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "data" / "raw" / "flights"

OPENFLIGHTS = "https://raw.githubusercontent.com/jpatokal/openflights/master/data"
BTS = ("https://transtats.bts.gov/PREZIP/"
       "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{y}_{m}.zip")

STATIC = ["airports", "airlines", "routes"]


def tls_context(insecure: bool):
    """Verify against the OS trust store, not certifi.

    Corporate networks inspect HTTPS by re-signing it with their own CA.
    Windows trusts that CA - the browser works - but Python ships its own
    bundle and every request dies with CERTIFICATE_VERIFY_FAILED.
    """
    if insecure:
        return False
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        return True


def human(n: int | None) -> str:
    if not n:
        return "?"
    f = float(n)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if f < 1024 or unit == "GiB":
            return f"{f:,.1f} {unit}"
        f /= 1024
    return f"{f:,.1f} GiB"


def remote_size(client: httpx.Client, url: str) -> tuple[int | None, str | None]:
    """Size, plus WHY if we could not get it. Falls back to a ranged GET
    because some proxies forward GET while blocking HEAD outright."""
    why = []
    for kind, call in (("HEAD", lambda: client.head(url, timeout=45.0,
                                                    follow_redirects=True)),
                       ("ranged GET", lambda: client.get(
                           url, headers={"Range": "bytes=0-0"},
                           timeout=45.0, follow_redirects=True))):
        try:
            r = call()
            if r.status_code == 206:
                cr = r.headers.get("content-range", "")
                if "/" in cr:
                    return int(cr.rsplit("/", 1)[1]), None
            if r.status_code == 200:
                n = int(r.headers.get("content-length", 0))
                if n:
                    return n, None
            why.append(f"{kind} -> HTTP {r.status_code}")
        except httpx.HTTPError as e:
            why.append(f"{kind} -> {type(e).__name__}: {e}")
    return None, "; ".join(why)


def download(client: httpx.Client, url: str, dest: Path,
             retries: int = 5) -> bool:
    total, why = remote_size(client, url)
    if total is None:
        print(f"    ! cannot reach {dest.name}\n      {why}", file=sys.stderr)
        return False

    if dest.exists() and dest.stat().st_size == total:
        print(f"    = {dest.name} already complete ({human(total)})")
        return True

    for attempt in range(1, retries + 1):
        have = dest.stat().st_size if dest.exists() else 0
        if have == total:
            return True
        if have > total:
            dest.unlink()
            have = 0
        headers = {"Range": f"bytes={have}-"} if have else {}
        started, last = time.monotonic(), have
        try:
            with client.stream("GET", url, headers=headers, timeout=120.0,
                               follow_redirects=True) as r:
                if r.status_code not in (200, 206):
                    raise httpx.HTTPError(f"status {r.status_code}")
                with dest.open("ab" if have else "wb") as fh:
                    for chunk in r.iter_bytes(1 << 20):
                        fh.write(chunk)
                        last += len(chunk)
                        if last % (16 << 20) < (1 << 20):
                            el = max(time.monotonic() - started, 1e-6)
                            print(f"      {dest.name}: "
                                  f"{100.0 * last / total:5.1f}%  "
                                  f"{(last - have) / el / 1048576:.1f} MiB/s")
        except (httpx.HTTPError, OSError) as e:
            print(f"    ~ {dest.name} attempt {attempt}/{retries}: {e}",
                  file=sys.stderr)
            time.sleep(min(2 ** attempt, 30))
            continue
        if dest.exists() and dest.stat().st_size == total:
            el = max(time.monotonic() - started, 1e-6)
            print(f"    + {dest.name} {human(total)} in {el:,.0f}s")
            return True
    print(f"    ! {dest.name} FAILED after {retries} attempts", file=sys.stderr)
    return False


def month_url(ym: str) -> tuple[str, str]:
    m = re.fullmatch(r"(\d{4})-(\d{2})", ym)
    if not m:
        raise SystemExit(f"bad month {ym!r}, want YYYY-MM (e.g. 2025-01)")
    y, mo = m.group(1), str(int(m.group(2)))
    return BTS.format(y=y, m=mo), f"bts_{y}_{mo}.zip"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", nargs="*", default=["2025-01"],
                    help="BTS months as YYYY-MM; empty for routes only")
    ap.add_argument("--no-static", action="store_true",
                    help="skip the OpenFlights files")
    ap.add_argument("--insecure", action="store_true",
                    help="skip TLS verification; corporate interception only")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    plan: list[tuple[str, Path]] = []
    if not args.no_static:
        plan += [(f"{OPENFLIGHTS}/{n}.dat", DEST / f"{n}.dat") for n in STATIC]
    for ym in args.months:
        url, name = month_url(ym)
        plan.append((url, DEST / name))

    DEST.mkdir(parents=True, exist_ok=True)
    verify = tls_context(args.insecure)
    if args.insecure:
        print("  ! TLS verification DISABLED (--insecure)", file=sys.stderr)

    headers = {"User-Agent": "okg-flights/0.1 (+research; resumable)"}
    with httpx.Client(headers=headers, http2=False, verify=verify) as client:
        if args.dry_run:
            total = 0
            for url, dest in plan:
                sz, why = remote_size(client, url)
                total += sz or 0
                print(f"  {dest.name:<28} {human(sz) if sz else 'UNAVAILABLE':>12}"
                      f"  {'(on disk)' if dest.exists() else ''}")
                if sz is None:
                    print(f"       {why}")
            print(f"\n{len(plan)} files, {human(total)} total")
            return 0

        ok = failed = 0
        for url, dest in plan:
            print(f"  {dest.name}")
            if download(client, url, dest):
                ok += 1
            else:
                failed += 1

    print(f"\ndone: {ok} complete, {failed} failed")
    if failed and not ok:
        print("""
NOTHING downloaded. The reason is printed above each file.

  "CERTIFICATE_VERIFY_FAILED"
      Your network inspects HTTPS. Install truststore and retry:
          pip install truststore
  "ConnectError"
      Behind a proxy. Set HTTPS_PROXY and HTTP_PROXY, then retry.
  "HTTP 403" / "404"
      A web filter is blocking the host, or BTS has not published that
      month yet - it can lag by one to two weeks. Try an earlier month.
""", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
