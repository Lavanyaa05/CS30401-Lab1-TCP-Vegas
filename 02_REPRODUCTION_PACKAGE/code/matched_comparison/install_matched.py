"""Safely integrate adaptive relearning into the exact measured refresh tree."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys

from common import HERE, read_json, reference, sha, verify_package, write_json

CC = 'src/internet/model/tcp-vegas.cc'
HH = 'src/internet/model/tcp-vegas.h'
HELPER = 'scratch/main_satnet/vegas-experiment.h'
DETECTOR = 'src/internet/model/adaptive-basertt-detector.h'

def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'Expected exactly one integration anchor: {old!r}')
    return text.replace(old, new)

def transform(original):
    result = dict(original)
    result[HH] = once(result[HH], '#include "tcp-congestion-ops.h"',
                      '#include "tcp-congestion-ops.h"\n#include <cstdint>')
    result[HH] = once(result[HH], '    Time m_baseRttWindow{Seconds(0)};',
                      '    bool m_adaptiveBaseRtt{false};\n    std::uint32_t m_shiftCount{0};\n'
                      '    std::int64_t m_lastAdaptiveResetNs{-1000000000000LL};\n'
                      '    Time m_baseRttWindow{Seconds(0)};')
    result[CC] = once(result[CC], '                            .AddAttribute("BaseRttWindow",',
        '''                            .AddAttribute("AdaptiveBaseRtt",
                                          "Enable conditional persistent BaseRTT relearning",
                                          BooleanValue(false),
                                          MakeBooleanAccessor(&TcpVegas::m_adaptiveBaseRtt),
                                          MakeBooleanChecker())
                            .AddAttribute("BaseRttWindow",''')
    result[CC] = once(result[CC], '#include "ns3/boolean.h"',
                      '#include "ns3/boolean.h"\n#include "ns3/abort.h"\n#include "adaptive-basertt-detector.h"')
    result[CC] = once(result[CC], '      m_baseRttWindow(sock.m_baseRttWindow),',
        '      m_adaptiveBaseRtt(sock.m_adaptiveBaseRtt),\n'
        '      m_shiftCount(sock.m_shiftCount),\n'
        '      m_lastAdaptiveResetNs(sock.m_lastAdaptiveResetNs),\n'
        '      m_baseRttWindow(sock.m_baseRttWindow),')
    result[CC] = once(result[CC], '    if (rtt.IsZero())',
        '    NS_ABORT_MSG_IF(m_adaptiveBaseRtt && !m_baseRttWindow.IsZero(),\n'
        '                    "AdaptiveBaseRtt cannot be combined with BaseRttWindow");\n\n'
        '    if (rtt.IsZero())')
    anchor = '            const Time effectiveBaseRtt = std::min(m_baseRtt, m_minRtt);'
    result[CC] = once(result[CC], anchor, '''            if (m_adaptiveBaseRtt)
            {
                // Private helper stays in the model source directory; tcp-vegas.h
                // does not require an additional exported ns-3 public header.
                AdaptiveBaseRttDetector detector{m_shiftCount, m_lastAdaptiveResetNs};
                const bool reset = detector.Observe(Simulator::Now().GetNanoSeconds(),
                                                   m_minRtt.GetNanoSeconds(),
                                                   m_baseRtt.GetNanoSeconds());
                m_shiftCount = detector.shiftCount;
                m_lastAdaptiveResetNs = detector.lastResetNs;
                if (reset)
                {
                    const Time oldBaseRtt = m_baseRtt;
                    m_baseRtt = m_minRtt;
                    if (m_traceState)
                    {
                        std::clog << "VEGAS_ADAPTIVE_RESET,"
                                  << Simulator::Now().GetNanoSeconds() << ','
                                  << Simulator::GetContext() << ',' << static_cast<const void*>(this)
                                  << ',' << oldBaseRtt.GetNanoSeconds() << ','
                                  << m_baseRtt.GetNanoSeconds() << '\\n';
                    }
                }
            }
''' + anchor)
    result[HELPER] = once(result[HELPER], '    ns3::TcpVegas::GetTypeId();',
        '''    const char* adaptiveRaw = std::getenv("VEGAS_ADAPTIVE");
    const std::string adaptiveValue = adaptiveRaw ? adaptiveRaw : "0";
    NS_ABORT_MSG_IF(adaptiveValue != "0" && adaptiveValue != "1",
                    "VEGAS_ADAPTIVE must be 0 or 1");
    const bool adaptive = adaptiveValue == "1";
    NS_ABORT_MSG_IF(adaptive && seconds > 0.0,
                    "Adaptive relearning cannot be combined with sliding history");
    ns3::TcpVegas::GetTypeId();
    ns3::Config::SetDefault("ns3::TcpVegas::AdaptiveBaseRtt", ns3::BooleanValue(adaptive));''')
    result[HELPER] = once(result[HELPER], '<< enabled << \'\\n\';',
                          '<< enabled << ",adaptive=" << adaptive << \'\\n\';')
    result[DETECTOR] = (HERE / 'adaptive-basertt-detector.h').read_text()
    return result

def install(root, check=False):
    root = Path(root).expanduser().resolve(strict=True)
    verify_package()
    if (root / 'VERSION').read_text().strip() != '3.48':
        raise ValueError('Expected course ns-3.48')
    expected = reference()['sources']
    marker = root.parent / (root.name + '-matched-install.json')
    if marker.exists():
        installed = read_json(marker)
        if installed['installer_sha256'] != sha(Path(__file__)) or installed['detector_sha256'] != sha(HERE / 'adaptive-basertt-detector.h'):
            raise ValueError('Installer version differs from installed version; reconcile before updating')
        for name, digest in installed['source_sha256'].items():
            if sha(root / name) != digest:
                raise ValueError('Installed source changed: ' + name)
        print('Identical matched implementation already installed; no changes made.')
        return
    for name, digest in expected.items():
        if sha(root / name) != digest:
            raise ValueError('Measured refresh source mismatch: ' + name)
    if (root / DETECTOR).exists():
        raise ValueError('Unexpected detector header; no files changed')
    originals = {name: (root / name).read_text() for name in [CC, HH, HELPER]}
    changed = transform(originals)
    if check:
        print('Exact measured refresh sources verified; all integration anchors found. No changes made.')
        return
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = root.parent / ('matched-backup-' + stamp)
    for name in originals:
        target = backup / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / name, target)
    try:
        for name, content in changed.items():
            (root / name).write_text(content, newline='\n')
        hashes = {name: sha(root / name) for name in list(expected) + [DETECTOR]}
        write_json(marker, dict(installer_sha256=sha(Path(__file__)),
                   detector_sha256=sha(HERE / 'adaptive-basertt-detector.h'),
                   source_sha256=hashes, backup=str(backup)))
    except BaseException:
        for name in originals:
            shutil.copy2(backup / name, root / name)
        (root / DETECTOR).unlink(missing_ok=True)
        marker.unlink(missing_ok=True)
        raise
    print('Installed matched implementation. Backup:', backup)
    print('Build next: cd "$NS3_DIR" && ./ns3 build main_satnet')

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('ns3_dir', type=Path)
    p.add_argument('--check', action='store_true')
    a = p.parse_args()
    install(a.ns3_dir, a.check)

if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as error:
        sys.exit(str(error))
