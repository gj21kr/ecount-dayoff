# Leave service

Run one worker. TEAM_CONFIG_FILE points to the private team JSON; DATA_DIR and LEAVE_DIR point to private state and read-only PDFs.
GET /api/dashboard returns leave events only. POST /api/sync refreshes PDFs. Midnight sync uses Asia/Seoul.
The optional eCount snapshot is validated and deduplicated against PDFs. Unknown names remain unassigned; snapshot names must belong to the configured roster.
Calendar fetching is disabled. Old cache is not served. No passwords or source URLs are sent to clients.
All runtime data belongs under the ignored .credentials directory or an explicitly mounted external private source.

