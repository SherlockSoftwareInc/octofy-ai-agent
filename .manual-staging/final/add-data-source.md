# Add Data Source

To add a new database connection:

1. Click **Add new DB Connection** from the **File** menu, or click the add button on the toolbar (its tooltip reads **Add new database connection**).
2. The **New Connection Dialog** opens.
3. Select the **Connection Type**:
   - **SQL Server connection**
   - **ODBC DSN connection**
   - **PostgreSQL connection**
   - **MySQL connection**
   - **Oracle connection**
4. Fill in the fields for the selected connection type (see below).
5. (Optional) select an **Agent** in the **Octofy AI Agent** section.
6. Click **OK**.

## SQL Server Connection

When **SQL Server connection** is selected, fill in the following fields:

- **Server name** — Enter the name or address of the SQL Server instance.
- **Database name** — Type a name or select from the drop-down list. Octofy will attempt to retrieve available databases from the server when the server name field loses focus.
- **Authentication** — Choose one of the following authentication methods:
  - **Windows Authentication** — Uses the current Windows credentials. No user name or password is required.
  - **SQL Server authentication** — Enter a **User name** and **Password**.
  - **Active Directory Password Authentication** — Enter an Azure AD **User name** and **Password**.
  - **Active Directory Integrated Authentication** — Uses the current Azure AD identity. No credentials are required.
  - **Active Directory Interactive Authentication** — Launches an interactive Azure AD sign-in prompt. Only the **User name** is required.
  - **Service Principal Authentication** — Enter a **User name** (client ID) for service principal authentication.
  - **Managed Service Identity Authentication** — Uses managed identity / device code flow authentication. The **User name** and **Password** fields are enabled for this method.
- **User name** / **Password** — Enabled for the authentication methods that require credentials (see the list above).
- **Remember password** — Check to save the password for future sessions. It is enabled together with the password.
- **Encrypt connection** — Check to require an encrypted connection to the server.
- **Trust server certificate** — Check to skip certificate validation (useful for development or self-signed certificates).

### Connection to a SQL Server Using a Non-Default Port

If the SQL Server instance uses a port other than the default `1433`, enter the server name and port separated by a comma.

Example: `mydb.database.windows.net,14330`

## ODBC Connection

When **ODBC DSN connection** is selected:

- **DSN** — Select a Data Source Name from the drop-down list of available system/user DSNs.
- **Require manually login** — Check this option if the DSN requires credentials at connection time.
- **User name** / **Password** — Available when **Require manually login** is checked.
- **Remember password** — Check to save the password for future sessions.

The connection is named after the DSN. Existing ODBC connections are not converted to native provider connections automatically.

## PostgreSQL, MySQL, and Oracle Connections

These three connection types share the same credential-based editor. When one of them is selected, fill in the following fields:

- **Server name** — Host name or address of the database server. Include the port when the server does not use its default port, either as `host,5432` or as `host:5432`.
- **Database name** — Name of the database to open. For Oracle this is the service name. Octofy will attempt to retrieve available databases from the server when the server name field loses focus.
- **Authentication** — Fixed to a single credential option (**User name: / Password:**) for these providers.
- **User name** / **Password** — Credentials used to log on to the server.
- **Remember password** — Check to save the password for future sessions.
- **Encrypt connection** and **Trust server certificate** — Part of the shared editor. For PostgreSQL, MySQL, and Oracle these two check boxes do not change the generated connection string.

Behavior notes:

- Ports default to the standard port of the provider: PostgreSQL `5432`, MySQL `3306`, and Oracle `1521`.
- For Oracle, the port defaults to `1521` and the **Database name** is used as the service name (the default `orcl` is used when it is empty).
- Native connections are opened with a 15-second connect timeout.
- MariaDB servers are supported through the **MySQL connection** type. MariaDB is not a separate entry in the **Connection Type** list.
- Query parsing, SQL validation, and generated SQL follow the selected provider's dialect.

## AI Agent (Optional)

An AI agent can be associated with a connection to enable natural-language query assistance:

- Select a configured agent from the **Agent** drop-down list, or leave it set to **(None)**.
- Click **Add New Agent** to open the **AI Agent Manager** window and create or configure an agent.
- The **Octofy AI Agent** section stays disabled until the connection fields above are complete.
- When an agent is selected, Octofy will attempt to resolve the matching data source ID from the agent backend on clicking **OK**. If the data source cannot be resolved, a warning is shown and the connection is still saved.

See [AI Agent Manager window](ai-agent-manager-window.md) for the agent settings.

## Completing the Dialog

- Click **OK** to save the connection and add it to the data source list. **OK** is enabled once the required fields are filled in.
- Click **Cancel** to discard the changes and close the dialog.

[Back to Octofy User Manual](user-manual.md)

## Screenshots

![Add data source screen](images/Octofy_Add_data_source.png)

