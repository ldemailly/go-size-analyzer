import os.path
from argparse import ArgumentParser

import requests

from gsa import build_gsa
from merge import merge_covdata
from remote import load_remote_binaries, load_remote_for_tui_test, TestType, get_flag_str
from utils import *


def run_unit_tests():
    log("Running unit tests...")
    load_remote_for_tui_test()

    unit_path = os.path.join(get_project_root(), "covdata", "unit")

    unit_output_dir = os.path.join(get_project_root(), "results", "unit")
    ensure_dir(unit_output_dir)

    embed_out = run_process(
        [
            "go",
            "test",
            "-v",
            "-race",
            "-covermode=atomic",
            "-cover",
            "-tags=embed",
            "./...",
            f"-test.gocoverdir={unit_path}"
        ],
        "unit_embed",
        timeout=600,  # Windows runner is extremely slow
    )

    # test no tag
    normal_out = run_process(
        [
            "go",
            "test",
            "-v",
            "-race",
            "-covermode=atomic",
            "-cover",
            "./internal/webui",
            f"-test.gocoverdir={unit_path}",
        ],
        "unit",
        timeout=600,  # Windows runner is extremely slow
    )

    with open(os.path.join(unit_output_dir, "unit_embed.txt"), "w") as f:
        f.write(embed_out)
    with open(os.path.join(unit_output_dir, "unit.txt"), "w") as f:
        f.write(normal_out)

    log("Unit tests passed.")


failed = 0


def run_integration_tests(typ: str):
    i_failed = 0

    log(f"Running integration tests {typ}...")

    targets = load_remote_binaries(typ)

    if typ == "example":
        timeout = 2
    else:
        timeout = 60

    with build_gsa() as gsa:
        if typ == "example":
            run_web_test(gsa)

        all_tests = len(targets)
        completed_tests = 0

        skips = load_skip()

        for target in targets:
            head = f"[{completed_tests + 1}/{all_tests}] Test {target.name}"
            log(f"{head} start")

            if target.name in skips:
                log(f"{head} is skipped.")
                continue

            try:
                base = time.time()
                typ_base = base

                def report_typ(rtyp: TestType):
                    nonlocal typ_base
                    log(f"{head} {get_flag_str(rtyp)} passed in {format_time(time.time() - typ_base)}.")
                    typ_base = time.time()

                target.run_test(gsa, report_typ, timeout=timeout)
                log(f"{head} passed in {format_time(time.time() - base)}.")
            except Exception as e:
                log(f"{head} failed")

                if os.getenv("CI") is not None:
                    with open(os.getenv("GITHUB_STEP_SUMMARY"), "a") as f:
                        f.write(f"```log\n{str(e)}\n```\n")
                else:
                    print(e)

                i_failed += 1

            completed_tests += 1

    if i_failed == 0:
        log("Integration tests passed.")
    else:
        log(f"{i_failed} integration tests failed.")
        global failed
        failed += i_failed


def run_web_test(entry: str):
    log("Running web test...")

    env = os.environ.copy()
    env["GOCOVERDIR"] = get_covdata_integration_dir()
    env["OUTPUT_DIR"] = os.path.join(get_project_root(), "results", "web", "profiler")
    ensure_dir(env["OUTPUT_DIR"])

    port = find_unused_port()
    if port is None:
        raise Exception("Failed to find an unused port.")

    stdout_data, stderr_data = "", ""
    p = subprocess.Popen(
        args=[entry, "--web", "--listen", f"127.0.0.1:{port}", entry],
        text=True, cwd=get_project_root(),
        encoding="utf-8", env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    log(f"Waiting for the server to start on port {port}...")

    for line in iter(p.stdout.readline, ""):
        if "localhost" in line:
            break
        stdout_data += line

    time.sleep(1)

    if p.poll() is not None:
        stdout_data += p.stdout.read()
        stderr_data = p.stderr.read()

        log(f"stdout:\n {stdout_data}\n")
        log(f"stderr:\n {stderr_data}\n")

        raise Exception("Failed to start the server.")

    ret = requests.get(f"http://127.0.0.1:{port}").text

    assert_html_valid(ret)

    p.terminate()
    log("Web test passed.")


def get_parser() -> ArgumentParser:
    ap = ArgumentParser()

    ap.add_argument("--unit", action="store_true", help="Run unit tests.")
    ap.add_argument("--integration-example", action="store_true", help="Run integration tests for small binaries.")
    ap.add_argument("--integration-real", action="store_true", help="Run integration tests for large binaries.")
    ap.add_argument("--integration", action="store_true", help="Run all integration tests.")

    return ap


if __name__ == "__main__":
    parser = get_parser()
    args = parser.parse_args()

    init_dirs()

    if args.integration:
        args.integration_example = True
        args.integration_real = True

    if not args.unit and not args.integration_example and not args.integration_real:
        if os.getenv("CI") is None:
            args.unit = True
            args.integration_example = True
            args.integration_real = True
        else:
            raise Exception("Please specify a test type to run.")

    if args.unit:
        run_unit_tests()
    if args.integration_example:
        run_integration_tests("example")
    if args.integration_real:
        run_integration_tests("real")

    merge_covdata()

    if failed == 0:
        log("All tests passed.")
    else:
        log(f"{failed} tests failed.")
        exit(1)
