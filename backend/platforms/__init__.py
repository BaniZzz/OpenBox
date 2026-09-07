"""Third-party platform integrations behind the 授权中心 (authorization centre).

Each provider knows how to authorize a person, keep their token alive, read
their public profile, and (where the platform allows) publish content. The
API layer and the refresh task only ever talk to `service.py`.
"""
