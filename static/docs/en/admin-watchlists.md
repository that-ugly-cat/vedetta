## Admin — Watchlist

Each watchlist is a group of pilots monitored together. From this section you can create watchlists, configure them and manage their members.

### Creating a watchlist

Use the form at the top of the page. Enter a name, the Telegram chat ID (optional, can be added later) and the notification language. Click **Create watchlist**.

### Configuring the Telegram channel

Every watchlist **must** have an associated Telegram channel. The **@buco_buco_bot** bot must be present in the channel or group in order to send notifications.

To link a Telegram channel or group to a watchlist:

1. Add **@buco_buco_bot** to the channel or group
2. Send `/setup` in the channel
3. The bot replies with the chat ID (a number like `-100123456789`)
4. Paste it into the **Telegram chat_id** field of the watchlist and click **Save settings**

Without a chat ID and without the bot in the channel, no notifications are sent, but the watchlist and the map still work.

### Language

Notifications can be sent in **Italian** or **English**. This can be changed at any time without losing the configuration.

### Managing pilots

The **Pilots** section of each watchlist shows who is monitored in that group.

**Adding a pilot** — choose a user from the dropdown at the bottom of the table and click **+ Add pilot**. The user must already have a vedetta account.

**Removing a pilot** — click **✕** in the pilot's row. Their account remains active, but their devices will no longer be visible in the watchlist and they will no longer receive notifications for that group.

**Visible devices** — the Device column shows the devices the user has registered in their profile. If empty, they have not yet added any devices — remind them to do so from the "My devices" section.

### Deleting a watchlist

Click **🗑️ Delete** in the card header. Deletion is **irreversible**: it removes the watchlist, all its members and notification preferences. Devices and user accounts are not affected.
