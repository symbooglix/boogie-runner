* Clean up RunnerBase, it's a total mess. We should abstract out different
  "ToolRunners" (e.g. basic, systemd, docker) to clean up the code and keep
  things separate.
