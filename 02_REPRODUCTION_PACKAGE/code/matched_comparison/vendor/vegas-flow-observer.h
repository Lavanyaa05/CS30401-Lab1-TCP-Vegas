#ifndef VEGAS_FLOW_OBSERVER_H
#define VEGAS_FLOW_OBSERVER_H
#include "ns3/core-module.h"
#include "ns3/tcp-socket-base.h"
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <map>
#include <memory>
#include <string>

namespace vegas_eval
{
/** Counters from actual TCP Tx and Retransmission trace events. */
struct TcpBin
{
    uint64_t dataTx{0}, dataBytes{0}, retransmissions{0}, retransmittedBytes{0};
};

/** Sender-only observer; ignores ACK-only and SYN transmissions in data counts. */
struct FlowObserver
{
    std::string prefix; ///< Log prefix containing course flow ID.
    std::map<uint64_t, TcpBin> bins; ///< One-second counters.
    std::ofstream retx, state; ///< Detailed events for causal inspection.
    explicit FlowObserver(const std::string& p) : prefix(p)
    {
        retx.open(prefix + "_retransmissions.csv");
        state.open(prefix + "_cong_state.csv");
        NS_ABORT_MSG_IF(!retx || !state, "Cannot open TCP diagnostic files");
        retx << "time_ns,sequence,payload_bytes\n";
        state << "time_ns,old_state,new_state\n";
    }
    /** Count all transmitted data packets, including retransmissions. */
    void Tx(ns3::Ptr<const ns3::Packet> p, const ns3::TcpHeader&, ns3::Ptr<const ns3::TcpSocketBase>)
    {
        if (!p->GetSize()) return;
        auto& b = bins[ns3::Simulator::Now().GetNanoSeconds() / 1000000000LL];
        ++b.dataTx;
        b.dataBytes += p->GetSize();
    }
    /** Count ns-3's explicit data retransmission notification. */
    void Retx(ns3::Ptr<const ns3::Packet> p, const ns3::TcpHeader& h,
              const ns3::Address&, const ns3::Address&, ns3::Ptr<const ns3::TcpSocketBase>)
    {
        if (!p->GetSize()) return;
        const auto now = ns3::Simulator::Now().GetNanoSeconds();
        auto& b = bins[now / 1000000000LL];
        ++b.retransmissions;
        b.retransmittedBytes += p->GetSize();
        retx << now << ',' << h.GetSequenceNumber().GetValue() << ',' << p->GetSize() << '\n';
    }
    /** Record congestion state transitions; these alone do not prove packet loss. */
    void State(ns3::TcpSocketState::TcpCongState_t oldState, ns3::TcpSocketState::TcpCongState_t newState)
    {
        state << ns3::Simulator::Now().GetNanoSeconds() << ','
              << static_cast<unsigned>(oldState) << ',' << static_cast<unsigned>(newState) << '\n';
    }
    /** Flush at Simulator::Destroy, after the course simulation has finished. */
    void Finish()
    {
        std::ofstream out(prefix + "_extra_bins.csv");
        NS_ABORT_MSG_IF(!out, "Cannot write TCP counters");
        out << "start_s,data_tx_packets,data_tx_payload_bytes,retransmissions,retransmitted_payload_bytes\n";
        for (const auto& [second, b] : bins)
            out << second << ',' << b.dataTx << ',' << b.dataBytes << ','
                << b.retransmissions << ',' << b.retransmittedBytes << '\n';
        retx.close();
        state.close();
    }
};

/** Keep observer ownership until simulator teardown. */
inline void FinishFlow(std::shared_ptr<FlowObserver> observer) { observer->Finish(); }

/** Attach immediately after socket creation, before Connect() or any payload. */
inline void AttachFlow(ns3::Ptr<ns3::Socket> socket, const std::string& logsDir, uint64_t flowId)
{
    const char* enabled = std::getenv("VEGAS_EXTRA_TRACE");
    if (!enabled || std::string(enabled) != "1") return;
    auto observer = std::make_shared<FlowObserver>(logsDir + "/tcp_flow_" + std::to_string(flowId));
    bool a = socket->TraceConnectWithoutContext("Tx", ns3::MakeCallback(&FlowObserver::Tx, observer.get()));
    bool b = socket->TraceConnectWithoutContext("Retransmission", ns3::MakeCallback(&FlowObserver::Retx, observer.get()));
    bool c = socket->TraceConnectWithoutContext("CongState", ns3::MakeCallback(&FlowObserver::State, observer.get()));
    NS_ABORT_MSG_IF(!a || !b || !c, "Required TCP traces unavailable: expected ns-3.48");
    ns3::Simulator::ScheduleDestroy(&FinishFlow, observer);
    std::cout << "VEGAS_FLOW_BINDING," << flowId << '\n';
}
} // namespace vegas_eval
#endif
