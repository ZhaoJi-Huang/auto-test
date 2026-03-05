"""
Git 协作路由
提供脚本目录的 Git 操作 API：提交、拉取、状态查看、日志查看
操作主仓库，但只管理 scripts_repo_path 目录下的文件
"""

import os
import sys
import subprocess
import logging

from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

# Windows 下隐藏子进程窗口
_CREATION_FLAGS = 0
if sys.platform == "win32":
    _CREATION_FLAGS = subprocess.CREATE_NO_WINDOW


def _run_git(args, cwd, timeout=30):
    """执行 Git 命令

    Args:
        args: git 子命令参数列表，如 ["status", "--porcelain"]
        cwd: 工作目录
        timeout: 超时秒数

    Returns:
        (returncode, stdout, stderr)
    """
    cmd = ["git", "-C", cwd] + args
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            creationflags=_CREATION_FLAGS,
        )
        stdout = result.stdout.decode("utf-8", errors="ignore").strip()
        stderr = result.stderr.decode("utf-8", errors="ignore").strip()
        return result.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Git 命令超时（{timeout}s）: {' '.join(cmd)}")
    except FileNotFoundError:
        raise RuntimeError("Git 未安装或不在 PATH 中")


def create_git_routes(scripts_repo_path):
    """创建 Git 协作路由蓝图

    Args:
        scripts_repo_path: 脚本目录路径（在主仓库内）

    Returns:
        Flask Blueprint
    """
    bp = Blueprint("tv_git", __name__)

    # 找到主仓库根目录和脚本目录的相对路径
    abs_scripts = os.path.abspath(scripts_repo_path)
    try:
        result = subprocess.run(
            ["git", "-C", abs_scripts, "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=_CREATION_FLAGS,
        )
        repo_root = result.stdout.decode("utf-8", errors="ignore").strip()
    except Exception:
        repo_root = ""

    if not repo_root:
        # fallback: 假设 scripts 的父目录是仓库根
        repo_root = os.path.dirname(abs_scripts)

    repo_root = os.path.normpath(repo_root)
    # 脚本目录相对于仓库根的路径（用于 git 过滤）
    scripts_rel = os.path.relpath(abs_scripts, repo_root).replace("\\", "/")

    def _check_repo():
        """检查是否在有效 Git 仓库中"""
        git_dir = os.path.join(repo_root, ".git")
        if not os.path.isdir(git_dir):
            return False, "不在 Git 仓库中"
        return True, ""

    # ------------------------------------------------------------------
    # POST /api/tv/git/commit — 提交脚本变更到主仓库
    # ------------------------------------------------------------------
    @bp.route("/api/tv/git/commit", methods=["POST"])
    def git_commit():
        ok, err = _check_repo()
        if not ok:
            return jsonify({"success": False, "error": err}), 400

        body = request.get_json() or {}
        message = body.get("message", "").strip()
        if not message:
            message = "更新测试脚本"

        try:
            # 只添加脚本目录下的变更
            _run_git(["add", scripts_rel], cwd=repo_root)

            # 检查是否有暂存的变更
            rc, staged, _ = _run_git(["diff", "--cached", "--name-only"], cwd=repo_root)
            if not staged:
                return jsonify({"success": False, "error": "没有需要提交的变更"})

            file_count = len(staged.split("\n"))

            # 提交
            rc, stdout, stderr = _run_git(["commit", "-m", message], cwd=repo_root)
            if rc != 0:
                return jsonify({"success": False, "error": f"提交失败: {stderr or stdout}"})

            # 推送
            rc, stdout, stderr = _run_git(["push"], cwd=repo_root, timeout=60)
            if rc != 0:
                push_error = stderr or stdout
                if "Authentication" in push_error or "auth" in push_error.lower():
                    push_msg = "提交成功但推送失败：需要配置 Git 认证信息"
                elif "Could not resolve" in push_error or "unable to access" in push_error.lower():
                    push_msg = "提交成功但推送失败：网络不可用"
                else:
                    push_msg = f"提交成功但推送失败: {push_error}"
                return jsonify({"success": True, "message": push_msg, "data": {"committed": file_count, "pushed": False}})

            return jsonify({
                "success": True,
                "message": f"已提交并推送 {file_count} 个文件",
                "data": {"committed": file_count, "pushed": True},
            })

        except RuntimeError as e:
            return jsonify({"success": False, "error": str(e)})
        except Exception as e:
            logger.error("Git 提交异常: %s", e)
            return jsonify({"success": False, "error": f"Git 操作异常: {e}"})

    # ------------------------------------------------------------------
    # POST /api/tv/git/pull — 同步远程变更
    # ------------------------------------------------------------------
    @bp.route("/api/tv/git/pull", methods=["POST"])
    def git_pull():
        ok, err = _check_repo()
        if not ok:
            return jsonify({"success": False, "error": err}), 400

        try:
            rc, stdout, stderr = _run_git(["pull", "--ff-only"], cwd=repo_root, timeout=60)
            if rc != 0:
                error_msg = stderr or stdout
                if "conflict" in error_msg.lower():
                    return jsonify({"success": False, "error": "拉取失败：存在合并冲突，请手动解决"})
                if "Authentication" in error_msg or "auth" in error_msg.lower():
                    return jsonify({"success": False, "error": "拉取失败：需要配置 Git 认证信息"})
                return jsonify({"success": False, "error": f"拉取失败: {error_msg}"})

            updated = "Already up to date" not in stdout
            return jsonify({
                "success": True,
                "message": "已更新" if updated else "已是最新",
                "data": {"updated": updated, "output": stdout},
            })

        except RuntimeError as e:
            return jsonify({"success": False, "error": str(e)})
        except Exception as e:
            logger.error("Git pull 异常: %s", e)
            return jsonify({"success": False, "error": f"Git 操作异常: {e}"})

    # ------------------------------------------------------------------
    # GET /api/tv/git/status — 查看脚本目录的 Git 状态
    # ------------------------------------------------------------------
    @bp.route("/api/tv/git/status", methods=["GET"])
    def git_status():
        ok, err = _check_repo()
        if not ok:
            return jsonify({"success": False, "error": err}), 400

        try:
            # 只查看脚本目录的状态，-uall 展开未跟踪目录为单个文件
            rc, stdout, stderr = _run_git(
                ["status", "--porcelain", "-uall", "--", scripts_rel],
                cwd=repo_root,
            )
            if rc != 0:
                return jsonify({"success": False, "error": f"获取状态失败: {stderr}"})

            _STATUS_MAP = {
                "M": "modified", "A": "added", "D": "deleted",
                "R": "renamed", "C": "copied", "??": "new",
            }

            changed_files = []
            if stdout:
                for line in stdout.split("\n"):
                    if not line or len(line) < 4:
                        continue
                    code = line[:2].strip()
                    filepath = line[3:]
                    # 去掉脚本目录前缀，只显示相对文件名
                    prefix = scripts_rel + "/"
                    if filepath.startswith(prefix):
                        filepath = filepath[len(prefix):]
                    changed_files.append({
                        "status": _STATUS_MAP.get(code, code),
                        "file": filepath,
                    })

            return jsonify({
                "success": True,
                "data": {
                    "has_changes": len(changed_files) > 0,
                    "changed_files": changed_files,
                },
            })

        except RuntimeError as e:
            return jsonify({"success": False, "error": str(e)})
        except Exception as e:
            logger.error("Git status 异常: %s", e)
            return jsonify({"success": False, "error": f"Git 操作异常: {e}"})

    # ------------------------------------------------------------------
    # GET /api/tv/git/log — 查看脚本目录的提交历史
    # ------------------------------------------------------------------
    @bp.route("/api/tv/git/log", methods=["GET"])
    def git_log():
        ok, err = _check_repo()
        if not ok:
            return jsonify({"success": False, "error": err}), 400

        try:
            # 只查看涉及脚本目录的提交
            rc, stdout, stderr = _run_git(
                ["log", "--oneline", "-20", "--", scripts_rel],
                cwd=repo_root,
            )
            if rc != 0:
                if "does not have any commits" in stderr:
                    return jsonify({"success": True, "data": []})
                return jsonify({"success": False, "error": f"获取日志失败: {stderr}"})

            commits = []
            if stdout:
                for line in stdout.split("\n"):
                    line = line.strip()
                    if line:
                        parts = line.split(" ", 1)
                        commits.append({
                            "hash": parts[0],
                            "message": parts[1] if len(parts) > 1 else "",
                        })

            return jsonify({"success": True, "data": commits})

        except RuntimeError as e:
            return jsonify({"success": False, "error": str(e)})
        except Exception as e:
            logger.error("Git log 异常: %s", e)
            return jsonify({"success": False, "error": f"Git 操作异常: {e}"})

    return bp
