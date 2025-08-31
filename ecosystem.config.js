module.exports = {
    apps: [
        {
            name: "stars_site_backend",
            script: "./start_backend.sh"
        }, {
            name: "stars_site_admin",
            script: "./start_admin.sh"
        }, {
            name: "stars_site_workers",
            script: "uv",
            args: "run run_threads.py"
        }
    ]
}
