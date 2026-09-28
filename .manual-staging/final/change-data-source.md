# Change Data Source

You can change the active data source at any time while the **Query Editor** or the **Object Browser** is open.

## From the Toolbar

Click the **Data source** combo box on the toolbar and select a connection from the drop-down list. The object explorer and schema information are reloaded for the selected connection.

If the selected connection uses a file-based ODBC data source, a file picker opens automatically so you can choose the file before the connection is made.

For SQL Server connections that use SQL Server authentication, Active Directory Password Authentication, or Managed Service Identity Authentication, and for every PostgreSQL, MySQL, and Oracle connection, Octofy asks for the credentials in a log-on dialog before the connection is made.

## From the File Menu

- Click **File > Connect to ...**.
- Select a connection name from the submenu.

In the **Query Editor** the **File** menu also contains **Add new DB Connection** and **Manage DB Connections**. The **Object Browser** window offers **Connect to ...** and **Close** only.

## Status Bar

After a connection is established, the status bar at the bottom of the window shows the connected server name and database name for a SQL Server connection. For other connection types the status bar shows the DSN instead, and the database label is hidden; PostgreSQL, MySQL, and Oracle connections do not show a server or database label here.

While a connection is being opened, the status bar shows the connection being opened, in the form `Connect to <connection name>...`.

The SQL dialect and identifier quoting follow the selected connection: SQL Server connections quote identifiers with `[ ]`, while other database types use `" "`.

## Managing Connections

To add, edit, or remove saved connections, click **File > Manage DB Connections** in the Query Editor. After closing the Manage Connections dialog, the toolbar combo box and the **Connect to ...** submenu are refreshed automatically.

[Back to Octofy User Manual](user-manual.md)
