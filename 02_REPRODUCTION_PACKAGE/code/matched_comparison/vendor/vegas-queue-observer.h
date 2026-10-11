// Experiment instrumentation for ns-3.48. This header changes no network decisions.
#ifndef VEGAS_QUEUE_OBSERVER_H
#define VEGAS_QUEUE_OBSERVER_H
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/traffic-control-layer.h"
#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

namespace vegas_eval
{
/** One-second aggregate queue statistics, including both data and ACK paths. */
struct QueueBin
{
    long double packetNs{0}; ///< Integral of summed device queue occupancy.
    uint32_t peakSingleQueue{0}; ///< Largest individual queue occupancy in this bin.
    uint64_t drops{0}; ///< Device queue Drop events.
    uint64_t tcDrops{0}; ///< Packets rejected before a stopped device queue.
};

/** Observe all exposed TxQueue attributes without polling or packet copying. */
class QueueObserver
{
  public:
    /** Per-device state; addresses stay stable through unique_ptr allocation. */
    struct Device
    {
        QueueObserver* owner{}; ///< Owning observer.
        ns3::Ptr<ns3::Queue<ns3::Packet>> queue; ///< Observed queue.
        uint32_t node{}, device{}, current{}, peak{}; ///< Device identity and occupancy.
        std::string type; ///< NetDevice runtime type.
        int64_t lastNs{0}; ///< Last integrated time.
        long double packetNs{0}; ///< Full-run occupancy integral.
        uint64_t drops{0}; ///< Queue drop count.
        /** Integrate the old occupancy up to a specified time, splitting at seconds. */
        void Advance(int64_t until)
        {
            until = std::min(until, owner->m_endNs);
            while (lastNs < until)
            {
                const auto bin = static_cast<size_t>(lastNs / 1000000000LL);
                const int64_t next = std::min(until, static_cast<int64_t>((bin + 1) * 1000000000LL));
                const long double area = static_cast<long double>(current) * (next - lastNs);
                packetNs += area;
                owner->m_bins.at(bin).packetNs += area;
                owner->m_bins.at(bin).peakSingleQueue =
                    std::max(owner->m_bins.at(bin).peakSingleQueue, current);
                lastNs = next;
            }
        }
        /** Handle every queue occupancy transition, including short bursts. */
        void Change(uint32_t oldValue, uint32_t newValue)
        {
            NS_ABORT_MSG_IF(oldValue != current, "Queue observer lost an occupancy transition");
            const auto now = ns3::Simulator::Now().GetNanoSeconds();
            Advance(now);
            current = newValue;
            peak = std::max(peak, newValue);
            if (now < owner->m_endNs)
            {
                auto& bin = owner->m_bins.at(now / 1000000000LL);
                bin.peakSingleQueue = std::max(bin.peakSingleQueue, newValue);
            }
        }
        /** Count only queue Drop events; no double-counting MacTxDrop. */
        void Drop(ns3::Ptr<const ns3::Packet> p)
        {
            const auto now = ns3::Simulator::Now().GetNanoSeconds();
            if (now >= owner->m_endNs) return;
            ++drops;
            ++owner->m_bins.at(now / 1000000000LL).drops;
            owner->m_dropFile << now << ',' << node << ',' << device << ','
                             << p->GetUid() << ',' << p->GetSize() << '\n';
        }
    };

    /** Observe the separate no-qdisc, stopped-device-queue drop branch. */
    static void TcDrop(QueueObserver* owner, uint32_t node, ns3::Ptr<const ns3::Packet> p)
    {
        const auto now = ns3::Simulator::Now().GetNanoSeconds();
        if (now >= owner->m_endNs) return;
        ++owner->m_bins.at(now / 1000000000LL).tcDrops;
        owner->m_tcDropFile << now << ',' << node << ',' << p->GetUid() << ',' << p->GetSize() << '\n';
    }

    /** Bind queues after topology creation and before Simulator::Run(). */
    QueueObserver(const std::string& logsDir, int64_t endNs)
        : m_dir(logsDir), m_endNs(endNs), m_bins((endNs + 999999999LL) / 1000000000LL)
    {
        NS_ABORT_MSG_IF(endNs <= 0, "Invalid simulation end time");
        m_dropFile.open(m_dir + "/queue_drop_events.csv");
        NS_ABORT_MSG_IF(!m_dropFile, "Cannot open queue drop log");
        m_dropFile << "time_ns,node,device,packet_uid,packet_bytes\n";
        m_tcDropFile.open(m_dir + "/tc_drop_events.csv");
        NS_ABORT_MSG_IF(!m_tcDropFile, "Cannot open traffic-control drop log");
        m_tcDropFile << "time_ns,node,packet_uid,packet_bytes\n";
        uint32_t unobserved = 0;
        for (auto it = ns3::NodeList::Begin(); it != ns3::NodeList::End(); ++it)
        {
            auto node = *it;
            auto tc = node->GetObject<ns3::TrafficControlLayer>();
            if (tc)
            {
                bool ok = tc->TraceConnectWithoutContext("TcDrop",
                    ns3::MakeBoundCallback(&QueueObserver::TcDrop, this, node->GetId()));
                NS_ABORT_MSG_IF(!ok, "Traffic-control drop trace unavailable");
                m_tcLayers.emplace_back(tc, node->GetId());
            }
            for (uint32_t i = 0; i < node->GetNDevices(); ++i)
            {
                auto nd = node->GetDevice(i);
                ns3::PointerValue value;
                if (!nd->GetAttributeFailSafe("TxQueue", value))
                {
                    if (nd->GetInstanceTypeId().GetName() != "ns3::LoopbackNetDevice") ++unobserved;
                    continue;
                }
                auto q = value.Get<ns3::Queue<ns3::Packet>>();
                NS_ABORT_MSG_IF(!q, "TxQueue is not a Queue<Packet>");
                auto d = std::make_unique<Device>();
                d->owner = this;
                d->queue = q;
                d->node = node->GetId();
                d->device = i;
                d->type = nd->GetInstanceTypeId().GetName();
                d->current = q->GetNPackets();
                d->peak = d->current;
                bool a = q->TraceConnectWithoutContext("PacketsInQueue", ns3::MakeCallback(&Device::Change, d.get()));
                bool b = q->TraceConnectWithoutContext("Drop", ns3::MakeCallback(&Device::Drop, d.get()));
                NS_ABORT_MSG_IF(!a || !b, "Required queue trace could not be connected");
                m_devices.push_back(std::move(d));
            }
        }
        NS_ABORT_MSG_IF(m_devices.empty() || unobserved,
                        "Incomplete queue coverage: check device types in this scenario");
        std::cout << "VEGAS_QUEUE_BINDINGS," << m_devices.size() << '\n';
    }

    /** Save exact time-weighted occupancy after Run() and before Destroy(). */
    void Finish()
    {
        NS_ABORT_MSG_IF(ns3::Simulator::Now().GetNanoSeconds() != m_endNs,
                        "Simulation did not reach its configured stop time");
        std::ofstream perDevice(m_dir + "/queue_devices.csv");
        std::ofstream bins(m_dir + "/network_queue_bins.csv");
        NS_ABORT_MSG_IF(!perDevice || !bins, "Cannot write queue statistics");
        perDevice << "node,device,type,mean_packets,peak_packets,queue_drops\n";
        perDevice << std::setprecision(12);
        for (auto& d : m_devices)
        {
            d->Advance(m_endNs);
            perDevice << d->node << ',' << d->device << ',' << d->type << ','
                      << static_cast<double>(d->packetNs / m_endNs) << ','
                      << d->peak << ',' << d->drops << '\n';
            d->queue->TraceDisconnectWithoutContext("PacketsInQueue", ns3::MakeCallback(&Device::Change, d.get()));
            d->queue->TraceDisconnectWithoutContext("Drop", ns3::MakeCallback(&Device::Drop, d.get()));
        }
        bins << "start_s,end_s,total_queued_mean_packets,max_single_queue_packets,queue_drops,tc_drops,total_buffer_drops\n";
        bins << std::setprecision(12);
        for (size_t i = 0; i < m_bins.size(); ++i)
        {
            const int64_t start = i * 1000000000LL;
            const int64_t stop = std::min<int64_t>(m_endNs, start + 1000000000LL);
            bins << start / 1e9 << ',' << stop / 1e9 << ','
                 << static_cast<double>(m_bins[i].packetNs / (stop - start)) << ','
                 << m_bins[i].peakSingleQueue << ',' << m_bins[i].drops << ',' << m_bins[i].tcDrops
                 << ',' << m_bins[i].drops + m_bins[i].tcDrops << '\n';
        }
        for (auto& [tc, node] : m_tcLayers)
            tc->TraceDisconnectWithoutContext("TcDrop", ns3::MakeBoundCallback(&QueueObserver::TcDrop, this, node));
        m_dropFile.close();
        m_tcDropFile.close();
    }
  private:
    std::string m_dir; ///< Output log directory.
    int64_t m_endNs; ///< Expected simulation stop time.
    std::vector<QueueBin> m_bins; ///< Fixed one-second measurement intervals.
    std::vector<std::unique_ptr<Device>> m_devices; ///< All observed device queues.
    std::ofstream m_dropFile; ///< Detailed queue drop events.
    std::ofstream m_tcDropFile; ///< Detailed pre-queue traffic-control drops.
    std::vector<std::pair<ns3::Ptr<ns3::TrafficControlLayer>, uint32_t>> m_tcLayers; ///< Node-level trace owners.
};
} // namespace vegas_eval
#endif
