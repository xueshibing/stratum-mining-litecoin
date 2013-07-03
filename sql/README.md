#SQL Instructions
When VARDIFF_ENABLED = False, the default database from mmcfe, mmcfe-ng will work for stratum.

If using VARDIFF, please apply the sql layout.  The SQL layout is the default from mmcfe-ng with diffifulty colums added for vardiff. For the default layout please apply stratum_default_layout.sql

    mysql -u user -p database < sql/stratum_default_layout.sql
