#!/usr/bin/env python3
import argparse
import sys
from ldap3 import Server, Connection, ALL, SUBTREE

LDAP_HOST = "localhost"
LDAP_PORT = 3389
BIND_DN = "cn=admin,dc=dewcis,dc=com"
BIND_PW = "adminpass"
BASE_DN = "dc=dewcis,dc=com"


def query_group(group_name):
    server = Server(LDAP_HOST, port=LDAP_PORT, get_info=ALL)

    try:
        conn = Connection(server, BIND_DN, BIND_PW, auto_bind=True)
    except Exception as e:
        print(f"Error: could not connect to LDAP server: {e}", file=sys.stderr)
        sys.exit(1)

    # Step 1: Find the group
    conn.search(
        search_base=f"ou=groups,{BASE_DN}",
        search_filter=f"(cn={group_name})",
        search_scope=SUBTREE,
        attributes=["cn", "gidNumber", "memberUid"]
    )

    if not conn.entries:
        print(f"Error: group '{group_name}' not found in directory.")
        sys.exit(1)

    group = conn.entries[0]
    gid = group.gidNumber.value
    members = group.memberUid.values if group.memberUid else []

    print(f"Group: {group_name} (gidNumber: {gid})")
    print("Members:")

    # Step 2: Look up each member
    for uid in members:
        conn.search(
            search_base=f"ou=users,{BASE_DN}",
            search_filter=f"(uid={uid})",
            search_scope=SUBTREE,
            attributes=["uid", "cn", "homeDirectory"]
        )
        if conn.entries:
            user = conn.entries[0]
            print(f"  {user.uid.value} | {user.cn.value} | {user.homeDirectory.value}")

    conn.unbind()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query LDAP group members.")
    parser.add_argument("group", help="Group name to query")
    args = parser.parse_args()
    query_group(args.group)