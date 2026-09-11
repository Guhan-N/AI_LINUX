from linagent.tools.automation.shell import ShellSession, execute_shell_command

def test_shell_dangerous_filter():
    session = ShellSession()
    
    # Dangerous commands
    safe, reason = session.is_safe("rm -rf /")
    assert safe is False
    assert "Dangerous" in reason

    safe, reason = session.is_safe("rm -rf /*")
    assert safe is False

    safe, reason = session.is_safe("mkfs.ext4 /dev/sda1")
    assert safe is False

    # Safe commands
    safe, reason = session.is_safe("ls -la /var/log")
    assert safe is True

    safe, reason = session.is_safe("cat /etc/hosts")
    assert safe is True

def test_shell_execution():
    session = ShellSession()
    res = session.execute("echo 'LinAgent Rocks'")
    assert res.success is True
    assert "LinAgent Rocks" in res.output

def test_shell_blocked_command():
    session = ShellSession()
    res = session.execute("rm -rf /")
    assert res.success is False
    assert "SAFETY VIOLATION" in res.error
