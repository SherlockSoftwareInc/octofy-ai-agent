# Manage Data Sources

Use the **Manage Connections** dialog to add, edit, delete, reorder, and test data sources.

## Open the Manage Connections Dialog

- In the main window, open the **File** menu.
- Click **Manage DB Connections**.

## Manage an Existing Data Source

- Select a connection from the **Connections** list.
- Update values in the right panel.
- Changed values are kept with the selected connection and are written to the connection settings file when you click **OK**. You can also move to another connection in the list before saving.

### SQL Server connection

Available fields/options:

- **Name**
- **Server name**
- **Database name**
- **Authentication**
  - Windows Authentication
  - SQL Server authentication
  - Active Directory Password Authentication
  - Active Directory Integrated Authentication
  - Active Directory Interactive Authentication
  - Service Principal Authentication
  - Managed Service Identity Authentication
- **User name** and **Password** (enabled for applicable authentication types: SQL Server authentication, Active Directory Password Authentication, and Managed Service Identity Authentication enable both; Active Directory Interactive Authentication and Service Principal Authentication enable the user name only)
- **Remember password**
- **Encrypt connection**
- **Trust server certificate**

### ODBC DSN connection

Available fields/options:

- **ODBC DSN**
- **Require manually login**
- **User name** and **Password** (when manual login is enabled)
- **Remember password** (enabled when password is entered)

The connection name is the DSN name; the **Name** box is not editable for an ODBC connection.

### PostgreSQL, MySQL, and Oracle connection

Available fields/options:

- **Name**
- **Server name** (include a non-default port as `host,port`, for example `pg.example.com,5432`)
- **Database name** (for Oracle this is the service name)
- **User name** and **Password**
- **Remember password**
- **Encrypt connection**
- **Trust server certificate**

Behavior notes:

- Native provider items use provider-aware connection and SQL dialect validation; parsing and generated SQL follow the selected provider.
- `Encrypt connection` and `Trust server certificate` affect SQL Server connections; for PostgreSQL, MySQL, and Oracle they do not change the generated connection string.
- Existing ODBC items are not automatically converted to native providers; keep ODBC for DSN-based connectivity, for Excel and Access files, and for other generic sources.
- MariaDB servers are used through the **MySQL connection** type; MariaDB is not a separate entry in the **Connection Type** list.
- For SQL Server, `Trust server certificate` follows the saved setting (an explicit unchecked value is honored).

### Optional: assign an Octofy AI Agent

In the **Octofy AI Agent** section:

- Select an **Agent** from the dropdown, or select **(None)**.
- Click **Add New Agent** to create or manage agents in the [AI Agent Manager window](ai-agent-manager-window.md).

The agent is assigned per connection and is saved with the connection when you click **OK**.

## Add a New Data Source

- Click **New** on the toolbar. The connection details group becomes **New**.
- Select **Connection Type**:
  - **SQL Server connection**
  - **ODBC DSN connection**
  - **PostgreSQL connection**
  - **MySQL connection**
  - **Oracle connection**
- Enter required fields.
- (Optional) choose an AI Agent.
- Click **Add** to add the connection to the list.
- Click **OK** to save the list and close the dialog.

## Reorder Data Sources

- Select a connection in the list.
- Click **Move up** or **Move down** on the toolbar.

## Delete a Data Source

- Select a connection in the list.
- Click **Delete**.
- Confirm the prompt.

## Test a Data Source

- Select a connection (or enter new connection details).
- Click **Test** on the toolbar.

The test validates connection settings first. If an AI Agent is selected, agent connectivity is also validated.

The result is reported in a **Connection testing** message: **Succeed!**, **Failed to connect to the database!**, or **AI agent test failed**. Testing does not save anything; use **Add** for a new connection or **OK** for an existing one.

## Save or Discard Changes

- Click **OK** to save changes and close. The connections are written to `connections.json` in the Octofy application data folder.
- Click **Cancel** to discard unsaved changes (the list is reloaded from disk) and close.

### SQL Server with a non-default port

If SQL Server does not use port `1433`, enter server and port together:

`serverName,port`

Example: `mydb.database.windows.net,14330`

[Back to Octofy User Manual](user-manual.md)

## Screenshots

![Manage data source screen](images/Octofy_Data_source_manage.png)

