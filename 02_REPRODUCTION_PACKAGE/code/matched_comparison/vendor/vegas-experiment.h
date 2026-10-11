// Original experiment configuration helper. The ns-3 model patch uses GPL-2.0-only.
#ifndef VEGAS_EXPERIMENT_H
#define VEGAS_EXPERIMENT_H

#include "ns3/core-module.h"
#include "ns3/tcp-vegas.h"

#include <cmath>
#include <cstdlib>
#include <iostream>
#include <string>

inline void ConfigureVegasExperiment()
{
    double seconds = 0.0;
    const char* raw = std::getenv("VEGAS_WINDOW_S");
    if (raw)
    {
        char* end = nullptr;
        seconds = std::strtod(raw, &end);
        NS_ABORT_MSG_IF(end == raw || *end != '\0' || !std::isfinite(seconds) ||
                            seconds < 0.0 || seconds > 3600.0,
                        "VEGAS_WINDOW_S must be a finite number from 0 to 3600");
    }
    const char* trace = std::getenv("VEGAS_TRACE");
    const bool enabled = trace && std::string(trace) == "1";
    ns3::TcpVegas::GetTypeId();
    ns3::Config::SetDefault("ns3::TcpVegas::BaseRttWindow", ns3::TimeValue(ns3::Seconds(seconds)));
    ns3::Config::SetDefault("ns3::TcpVegas::TraceState", ns3::BooleanValue(enabled));
    std::cout << "VEGAS_CONFIG,window_s=" << seconds << ",trace=" << enabled << '\n';
}
#endif

