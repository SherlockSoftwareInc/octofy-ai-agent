# Manage Data Sources
# Manage Data Sources

Use the **Manage Connections** dialog to add, edit, delete, reorder, and test data sources.

## Open the Manage Connections Dialog

- In the main window, open **File** menu.
- Click **Manage DB connections**.

## Manage an Existing Data Source

- Select a connection from the **Connections** list.
- Update values in the right panel.

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
- **User name** and **Password** (enabled for applicable authentication types)
- **Remember password**
- **Encrypt connection**
- **Trust server certificate**

### ODBC DSN connection

Available fields/options:

- **ODBC DSN**
- **Require manually login**
- **User name** and **Password** (when manual login is enabled)
- **Remember password** (enabled when password is entered)

### Optional: assign an Octofy AI Agent

In **Octofy AI Agent** section:

- Select an **Agent** from the dropdown.
- Click **Add New Agent** to create/manage agents.

## Add a New Data Source

- Click **New** on the toolbar.
- Select **Connection Type**:
  - **SQL Server connection**, or
  - **ODBC DSN connection**
- Enter required fields.
- (Optional) choose an AI Agent.
- Click **Add**.

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

The test validates connection settings. If an AI Agent is selected, agent connectivity is also validated.

## Save or Discard Changes

- Click **OK** to save changes and close.
- Click **Cancel** to discard unsaved changes and close.

### SQL Server with a non-default port

If SQL Server does not use port `1433`, enter server and port together:

`serverName,port`

Example: `mydb.database.windows.net,14330`

[Back to Octofy User Manual](user-manual.md)

## Screenshots

![Manage data source screen](images/Octofy_Data_source_manage.png)

