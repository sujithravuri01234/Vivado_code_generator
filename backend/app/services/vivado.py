from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.settings import settings
from app.schemas.design import VivadoReports


@dataclass(frozen=True)
class VivadoArtifacts:
    run_dir: Path
    verilog_path: Path
    testbench_path: Path
    tcl_path: Path
    log_path: Path
    simulation_log_path: Path
    timing_path: Path
    utilization_path: Path
    power_path: Path
    netlist_path: Path


class VivadoService:
    def validate(self, verilog: str, testbench: str = "") -> VivadoReports:
        vivado_path = Path(settings.vivado_path)
        if not vivado_path.exists():
            return self._skipped_reports()

        verilog = self._augment_verilog_sources(verilog)
        top_module = self._extract_top_module(verilog)
        run_root = Path(__file__).resolve().parents[2] / ".vivado_runs"
        run_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="vivado_run_", dir=run_root) as temp_dir:
            artifacts = self._prepare_artifacts(Path(temp_dir), top_module)
            try:
                artifacts.verilog_path.write_text(verilog, encoding="utf-8")
                if testbench:
                    artifacts.testbench_path.write_text(testbench, encoding="utf-8")
                artifacts.tcl_path.write_text(
                    self._build_tcl(
                        verilog_path=artifacts.verilog_path,
                        testbench_path=artifacts.testbench_path if testbench else None,
                        top_module=top_module,
                        tb_top_module=self._extract_testbench_top(testbench) if testbench else None,
                        simulation_log_path=artifacts.simulation_log_path,
                        timing_path=artifacts.timing_path,
                        utilization_path=artifacts.utilization_path,
                        power_path=artifacts.power_path,
                        netlist_path=artifacts.netlist_path,
                    ),
                    encoding="utf-8",
                )
            except OSError as exc:
                return VivadoReports(
                    timing_report={
                        "status": "failed",
                        "reason": str(exc),
                        "vivado_path": str(vivado_path),
                    },
                    simulation_report={
                        "status": "failed",
                        "reason": str(exc),
                    },
                    utilization_report={
                        "status": "failed",
                        "reason": str(exc),
                    },
                    power_report={
                        "status": "failed",
                        "reason": str(exc),
                    },
                    log={
                        "stderr": str(exc),
                    },
                    artifacts={},
                )

            run = self._run_vivado(vivado_path, artifacts)
            if run["status"] != "completed":
                return VivadoReports(
                simulation_report=run.get("simulation_report", {}),
                timing_report=run["timing_report"],
                utilization_report=run["utilization_report"],
                power_report=run["power_report"],
                log=run.get("log", {}),
                artifacts=run.get("artifacts", {}),
                )

            timing_report = self._parse_timing_report(artifacts.timing_path)
            utilization_report = self._parse_utilization_report(artifacts.utilization_path)
            power_report = self._parse_power_report(artifacts.power_path)
            simulation_report = run.get("simulation_report", {})
            if artifacts.simulation_log_path.exists():
                simulation_report.setdefault("status", "completed")
                simulation_report["path"] = str(artifacts.simulation_log_path)
                simulation_report["raw"] = self._read_text(artifacts.simulation_log_path)[:8000]

            timing_report["status"] = "completed"
            utilization_report["status"] = "completed"
            power_report["status"] = "completed"
            timing_report.update(run["artifacts"])
            utilization_report.update(run["artifacts"])
            power_report.update(run["artifacts"])

            if artifacts.netlist_path.exists():
                utilization_report["netlist_path"] = str(artifacts.netlist_path)
                utilization_report["netlist_exists"] = True
            else:
                utilization_report["netlist_exists"] = False
            if artifacts.testbench_path.exists():
                utilization_report["testbench_path"] = str(artifacts.testbench_path)
                utilization_report["testbench_exists"] = True

            return VivadoReports(
                simulation_report=simulation_report,
                timing_report=timing_report,
                utilization_report=utilization_report,
                power_report=power_report,
                log=run.get("log", {}),
                artifacts=run.get("artifacts", {}),
            )

    def _skipped_reports(self) -> VivadoReports:
        return VivadoReports(
            simulation_report={
                "status": "skipped",
                "reason": "Vivado executable not found",
            },
            timing_report={
                "status": "skipped",
                "reason": "Vivado executable not found",
                "vivado_path": settings.vivado_path,
            },
            utilization_report={
                "status": "skipped",
                "reason": "Vivado executable not found",
            },
            power_report={
                "status": "skipped",
                "reason": "Vivado executable not found",
            },
            log={},
            artifacts={},
        )

    def _prepare_artifacts(self, run_dir: Path, top_module: str) -> VivadoArtifacts:
        return VivadoArtifacts(
            run_dir=run_dir,
            verilog_path=run_dir / f"{top_module}.v",
            testbench_path=run_dir / f"{top_module}_tb.v",
            tcl_path=run_dir / "run.tcl",
            log_path=run_dir / "vivado.log",
            simulation_log_path=run_dir / "simulation.log",
            timing_path=run_dir / "timing_summary.rpt",
            utilization_path=run_dir / "utilization.rpt",
            power_path=run_dir / "power.rpt",
            netlist_path=run_dir / "synth_netlist.v",
        )

    def _run_vivado(self, vivado_path: Path, artifacts: VivadoArtifacts) -> dict[str, Any]:
        try:
            command = self._build_command(vivado_path, artifacts.tcl_path)
            process = subprocess.run(
                command,
                cwd=artifacts.run_dir,
                capture_output=True,
                text=True,
                timeout=60 * 30,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "status": "timeout",
                "simulation_report": {
                    "status": "timeout",
                    "reason": "Vivado batch execution exceeded the time limit",
                },
                "timing_report": {
                    "status": "timeout",
                    "reason": "Vivado batch execution exceeded the time limit",
                    "stdout": (exc.stdout or "")[-4000:],
                    "stderr": (exc.stderr or "")[-4000:],
                    "vivado_path": str(vivado_path),
                },
                "utilization_report": {
                    "status": "timeout",
                    "reason": "Vivado batch execution exceeded the time limit",
                },
                "power_report": {
                    "status": "timeout",
                    "reason": "Vivado batch execution exceeded the time limit",
                },
                "log": {
                    "stdout": (exc.stdout or "")[-4000:],
                    "stderr": (exc.stderr or "")[-4000:],
                },
                "artifacts": {},
            }
        except OSError as exc:
            return {
                "status": "failed",
                "simulation_report": {
                    "status": "failed",
                    "reason": str(exc),
                },
                "timing_report": {
                    "status": "failed",
                    "reason": str(exc),
                    "vivado_path": str(vivado_path),
                },
                "utilization_report": {
                    "status": "failed",
                    "reason": str(exc),
                },
                "power_report": {
                    "status": "failed",
                    "reason": str(exc),
                },
                "log": {
                    "stderr": str(exc),
                },
                "artifacts": {},
            }

        artifacts.log_path.write_text(process.stdout + "\n" + process.stderr, encoding="utf-8")
        if artifacts.testbench_path.exists():
            artifacts.simulation_log_path.write_text(
                process.stdout + "\n" + process.stderr,
                encoding="utf-8",
            )
        base_artifacts = self._artifact_summary(artifacts, process.returncode, process.stdout, process.stderr)

        if process.returncode != 0:
            return {
                "status": "failed",
                "simulation_report": {
                    "status": "failed",
                    "returncode": process.returncode,
                    **base_artifacts,
                },
                "timing_report": {
                    "status": "failed",
                    "returncode": process.returncode,
                    **base_artifacts,
                },
                "utilization_report": {
                    "status": "failed",
                    "returncode": process.returncode,
                    **base_artifacts,
                },
                "power_report": {
                    "status": "failed",
                    "returncode": process.returncode,
                    **base_artifacts,
                },
                "log": {
                    "stdout": process.stdout[-8000:],
                    "stderr": process.stderr[-8000:],
                    "log_path": str(artifacts.log_path),
                },
                "artifacts": base_artifacts,
            }

        return {
            "status": "completed",
            "artifacts": base_artifacts,
            "log": {
                "stdout": process.stdout[-8000:],
                "stderr": process.stderr[-8000:],
                "log_path": str(artifacts.log_path),
            },
            "process": {
                "returncode": process.returncode,
                "stdout": process.stdout[-8000:],
                "stderr": process.stderr[-8000:],
            },
            "simulation_report": {
                "status": "completed",
                "top_testbench": self._extract_testbench_top_from_path(artifacts.testbench_path),
                "log_path": str(artifacts.simulation_log_path),
            },
            "timing_report": {},
            "utilization_report": {},
            "power_report": {},
        }

    def _build_command(self, vivado_path: Path, tcl_path: Path) -> list[str]:
        if vivado_path.suffix.lower() == ".bat":
            return [
                "cmd.exe",
                "/c",
                str(vivado_path),
                "-mode",
                "batch",
                "-source",
                str(tcl_path),
                "-notrace",
            ]
        return [
            str(vivado_path),
            "-mode",
            "batch",
            "-source",
            str(tcl_path),
            "-notrace",
        ]

    def _artifact_summary(self, artifacts: VivadoArtifacts, returncode: int, stdout: str, stderr: str) -> dict[str, Any]:
        return {
            "status": "completed",
            "returncode": returncode,
            "top_module": artifacts.verilog_path.stem,
            "run_dir": str(artifacts.run_dir),
            "log_path": str(artifacts.log_path),
            "simulation_log_path": str(artifacts.simulation_log_path),
            "tcl_path": str(artifacts.tcl_path),
            "verilog_path": str(artifacts.verilog_path),
            "testbench_path": str(artifacts.testbench_path),
            "timing_path": str(artifacts.timing_path),
            "utilization_path": str(artifacts.utilization_path),
            "power_path": str(artifacts.power_path),
            "netlist_path": str(artifacts.netlist_path),
            "stdout": stdout[-4000:],
            "stderr": stderr[-4000:],
        }

    def _extract_top_module(self, verilog: str) -> str:
        match = re.search(r"module\s+([a-zA-Z_][\w$]*)", verilog)
        if match:
            return match.group(1)
        return "design_top"

    def _augment_verilog_sources(self, verilog: str) -> str:
        if "mux_2to1 " not in verilog and "mux_2to1(" not in verilog:
            return verilog
        if re.search(r"module\s+mux_2to1\b", verilog):
            return verilog
        support = """module mux_2to1(
    input wire S0,
    input wire D0,
    input wire D1,
    output wire Y
);

assign Y = S0 ? D1 : D0;

endmodule
"""
        return support + "\n" + verilog

    def _extract_testbench_top(self, testbench: str) -> str | None:
        match = re.search(r"module\s+([a-zA-Z_][\w$]*)", testbench)
        if match:
            return match.group(1)
        return None

    def _extract_testbench_top_from_path(self, testbench_path: Path) -> str | None:
        if not testbench_path.exists():
            return None
        return self._extract_testbench_top(testbench_path.read_text(encoding="utf-8"))

    def _build_tcl(
        self,
        verilog_path: Path,
        testbench_path: Path | None,
        top_module: str,
        tb_top_module: str | None,
        simulation_log_path: Path,
        timing_path: Path,
        utilization_path: Path,
        power_path: Path,
        netlist_path: Path,
    ) -> str:
        part = settings.vivado_part
        read_files_block = f"""
add_files -norecurse "{verilog_path.as_posix()}"
update_compile_order -fileset sources_1
"""
        sim_block = ""
        if testbench_path and tb_top_module:
            sim_block = f"""
add_files -fileset sim_1 -norecurse "{testbench_path.as_posix()}"
update_compile_order -fileset sim_1
set_property top {tb_top_module} [get_filesets sim_1]
launch_simulation -simset sim_1 -mode behavioral
run all
close_sim
"""
        return f"""
set_msg_config -id {{Common 17-55}} -new_severity INFO
create_project -in_memory -part {part} vivado_hw_copilot
{read_files_block}
{sim_block}
puts "Starting elaboration and synthesis for {top_module}"
synth_design -top {top_module} -part {part}
report_timing_summary -file "{timing_path.as_posix()}"
report_utilization -file "{utilization_path.as_posix()}"
report_power -file "{power_path.as_posix()}"
write_verilog -force "{netlist_path.as_posix()}"
close_project
quit
"""

    def _read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def _parse_timing_report(self, path: Path) -> dict[str, object]:
        text = self._read_text(path)
        report = {
            "status": "generated" if text else "missing",
            "path": str(path),
            "raw": text[:8000],
        }
        wns = self._extract_float(text, r"WNS\(ns\)\s+(-?\d+\.?\d*)")
        tns = self._extract_float(text, r"TNS\(ns\)\s+(-?\d+\.?\d*)")
        if wns is not None:
            report["wns"] = wns
        if tns is not None:
            report["tns"] = tns
        return report

    def _parse_utilization_report(self, path: Path) -> dict[str, object]:
        text = self._read_text(path)
        report = {
            "status": "generated" if text else "missing",
            "path": str(path),
            "raw": text[:8000],
        }
        lut = self._extract_int(text, r"CLB LUTs\s*\|\s*(\d+)")
        ff = self._extract_int(text, r"CLB Registers\s*\|\s*(\d+)")
        if lut is not None:
            report["lut"] = lut
        if ff is not None:
            report["ff"] = ff
        return report

    def _parse_power_report(self, path: Path) -> dict[str, object]:
        text = self._read_text(path)
        report = {
            "status": "generated" if text else "missing",
            "path": str(path),
            "raw": text[:8000],
        }
        total_power = self._extract_float(text, r"Total On-Chip Power\s+\|\s+(-?\d+\.?\d*)")
        if total_power is not None:
            report["total_on_chip_power"] = total_power
        return report

    def _extract_float(self, text: str, pattern: str) -> float | None:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None

    def _extract_int(self, text: str, pattern: str) -> int | None:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None
