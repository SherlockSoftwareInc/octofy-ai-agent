# Add Data Source

To add a new database connection:

1. Click **Add new DB connection** from the **File** menu, or click the **+** button on the toolbar.
2. The **New Connection** dialog opens.
3. Select the **Connection type**: **SQL Server** or **ODBC**.

## SQL Server Connection

When **SQL Server** is selected, fill in the following fields:

- **Server name** — Enter the name or address of the SQL Server instance.
- **Database name** — Type a name or select from the drop-down list. Octofy will attempt to retrieve available databases from the server when the server name field loses focus.
- **Authentication** — Choose one of the following authentication methods:
  - **Windows Authentication** — Uses the current Windows credentials. No user name or password is required.
  - **SQL Server Authentication** — Enter a **User name** and **Password**.
  - **Active Directory - Password** — Enter an Azure AD **User name** and **Password**.
  - **Active Directory - Integrated** — Uses the current Azure AD identity. No credentials are required.
  - **Active Directory - Interactive** — Launches an interactive Azure AD sign-in prompt.
  - **Active Directory - Service Principal** — Enter a **User name** (client ID) for service principal authentication.
  - **Active Directory - Device Code Flow** — Uses managed identity / device code flow authentication.
- **User name** / **Password** — Shown and required when the selected authentication method requires credentials.
- **Remember password** — Check to save the password for future sessions.
- **Encrypt connection** — Check to require an encrypted connection to the server.
- **Trust server certificate** — Check to skip certificate validation (useful for development or self-signed certificates).

### Connection to a SQL Server Using a Non-Default Port

If the SQL Server instance uses a port other than the default `1433`, enter the server name and port separated by a comma.

Example: `mydb.database.windows.net,14330`

## ODBC Connection

When **ODBC** is selected:

- **DSN** — Select a Data Source Name from the drop-down list of available system/user DSNs.
- **Require manual login** — Check this option if the DSN requires credentials at connection time.
- **User name** / **Password** — Available when **Require manual login** is checked.
- **Remember password** — Check to save the password for future sessions.

## AI Agent (Optional)

An AI agent can be associated with a connection to enable natural-language query assistance:

- Select a configured agent from the **AI Agent** drop-down list, or leave it set to **(None)**.
- Click **Manage Agents** to add or configure agents before completing the connection.
- When an agent is selected, Octofy will attempt to resolve the matching data source ID from the agent backend on clicking **OK**.

## Completing the Dialog

- Click **OK** to save the connection and add it to the data source list.
- Click **Cancel** to discard the changes.

[Back to Octofy User Manual](user-manual.md)

## Screenshots

![Add data source screen](images/Octofy_Add_data_source.png)

