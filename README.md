# epg-atlanta

Auto-updating XMLTV + M3U system for Atlanta OTA, FAST, and Faith channels.

## LocalNow Atlanta

The LocalNow Atlanta playlist and its custom XMLTV guide are refreshed daily by GitHub Actions. The guide is built from LocalNow's Atlanta EPG page and the WANF Atlanta News First page.

- Playlist: [localnow_atlanta.m3u](https://raw.githubusercontent.com/mingram751-afk/epg-atlanta/main/localnow_atlanta.m3u)
- Guide: [localnow_atlanta_epg.xml](https://raw.githubusercontent.com/mingram751-afk/epg-atlanta/main/localnow_atlanta_epg.xml)
- Updater: [tools/update_localnow_atlanta.py](tools/update_localnow_atlanta.py)

The updater refreshes stream URLs from the public Apsattv LocalNow playlist when available and keeps the checked-in entries as a fallback. WANF is retained as a LocalNow page URL if the external playlist does not provide a direct stream, so that entry may not play in IPTV apps that require HLS URLs.
