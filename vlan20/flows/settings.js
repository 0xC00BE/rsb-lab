module.exports = {
    adminAuth: {
        type: 'credentials',
        users: [{username: 'svc.nodered',
            password: require('fs').readFileSync('/data/admin.hash', 'utf8').trim(),
            permissions: '*'}]
    },
    credentialSecret: false, // Local generated credential file is excluded from Git.
    flowFile: 'flows.json',
    editorTheme: {projects: {enabled: false}},
    logging: {console: {level: 'info', metrics: false, audit: false}}
};
