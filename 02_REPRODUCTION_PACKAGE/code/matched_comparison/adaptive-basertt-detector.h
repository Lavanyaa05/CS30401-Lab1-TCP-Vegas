// Sender-only persistent shift detector. No route or queue information is used.
#ifndef MATCHED_ADAPTIVE_BASERTT_DETECTOR_H
#define MATCHED_ADAPTIVE_BASERTT_DETECTOR_H
#include <cstdint>

namespace ns3
{
struct AdaptiveBaseRttDetector
{
    std::uint32_t shiftCount{0};
    std::int64_t lastResetNs{-1000000000000LL}; // Seconds(-1000), as in the prototype

    // Called only at the prototype's eligible Vegas calculation site.
    bool Observe(std::int64_t nowNs, std::int64_t cycleMinNs, std::int64_t baseNs)
    {
        if (cycleMinNs > baseNs && cycleMinNs - baseNs > 3000000LL &&
            nowNs - lastResetNs > 10000000000LL)
        {
            ++shiftCount;
        }
        else
        {
            shiftCount = 0;
        }
        if (shiftCount < 5) return false;
        shiftCount = 0;
        lastResetNs = nowNs;
        return true;
    }
};
} // namespace ns3
#endif
