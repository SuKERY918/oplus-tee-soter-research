#!/usr/bin/env python3
import argparse
import re


def main():
    ap = argparse.ArgumentParser(description="Read widget texts from a uiautomator dump by resource-id.")
    ap.add_argument("xml")
    ap.add_argument("ids", nargs="+", metavar="RESOURCE_ID", help="e.g. security_status_soter_key")
    args = ap.parse_args()
    data = open(args.xml, encoding="utf-8", errors="replace").read()
    for rid in args.ids:
        pat = (
            r'text="([^"]*)"[^>]*resource-id="[^"]*:id/'
            + re.escape(rid)
            + r'"'
        )
        m = re.search(pat, data)
        print(f"{rid} = {m.group(1) if m else 'NOT FOUND'}")


if __name__ == "__main__":
    main()
