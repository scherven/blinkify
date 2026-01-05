//
//  ContentView.swift
//  blinkify
//
//  Created by Simon Chervenak on 1/5/26.
//

import SwiftUI

struct ContentView: View {
    @State private var isAvailable = false
    @State private var lastAvailabilityUpdate: String?
    @State private var lastRefreshed = Date()
    @State private var timer: Timer?
    @State private var isLoading = false
    
    private var placeId = "ChIJlf0s_HFLtokRRa9H_ouBaLM"
    private var apiKey = Key.key
    
    var body: some View {
            GeometryReader { geometry in
                ScrollView {
                    ZStack {
                        // Background color
                        (isAvailable ? Color.green : Color.red)
                            .frame(width: geometry.size.width, height: geometry.size.height)
                        
                        VStack {
                            // Last refreshed timestamp at top
                            Text("Last refreshed: \(formatDate(lastRefreshed))")
                                .foregroundColor(.white)
                                .padding()
                                .padding(.top, 80)
                                .font(.headline)
                            
                            Spacer()
                            
                            // Station status
                            VStack(spacing: 10) {
                                if let updateTime = lastAvailabilityUpdate {
                                    Text("Last updated: \(updateTime)")
                                        .font(.subheadline)
                                        .foregroundColor(.black)
                                        .padding(.horizontal, 12)
                                        .padding(.vertical, 6)
                                        .background(Color.white.opacity(0.9))
                                        .cornerRadius(8)
                                }
                                
                                if isLoading {
                                    ProgressView()
                                        .tint(.white)
                                }
                            }
                            
                            Spacer()
                        }
                        .frame(width: geometry.size.width, height: geometry.size.height)
                    }
                }
                .refreshable {
                    await refresh()
                }
            }
            .ignoresSafeArea()
            .onAppear {
                Task {
                    await refresh()
                }
                startTimer()
            }
            .onDisappear {
                stopTimer()
            }
        }
        
        func refresh() async {
            guard !isLoading else { return }
            isLoading = true
            
            // Check EV station availability
            let (available, updateTime) = await checkStationAvailability(placeId: placeId)
            isAvailable = available
            lastAvailabilityUpdate = updateTime
            lastRefreshed = Date()
            
            isLoading = false
        }
        
        func checkStationAvailability(placeId: String) async -> (Bool, String?) {
            guard let url = URL(string: "https://places.googleapis.com/v1/places/\(placeId)") else {
                print("Invalid URL")
                return (false, nil)
            }
            
            var request = URLRequest(url: url)
            request.httpMethod = "GET"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.setValue(apiKey, forHTTPHeaderField: "X-Goog-Api-Key")
            request.setValue("evChargeOptions", forHTTPHeaderField: "X-Goog-FieldMask")
            
            do {
                let (data, _) = try await URLSession.shared.data(for: request)
                let response = try JSONDecoder().decode(PlaceDetailsResponse.self, from: data)
                
                // Find the connector with the smallest maxChargeRateKw
                if let connectors = response.evChargeOptions?.connectorAggregation,
                   let slowestConnector = connectors.min(by: { ($0.maxChargeRateKw ?? 0) < ($1.maxChargeRateKw ?? 0) }) {
                    
                    let available = (slowestConnector.availableCount ?? 0) > 0
                    let updateTime = slowestConnector.availabilityLastUpdateTime.map { formatAvailabilityTime($0) }
                    
                    return (available, updateTime)
                }
                
                return (false, nil)
            } catch {
                print("Error fetching station status: \(error)")
                if let data = try? await URLSession.shared.data(for: request).0 {
                    print("Response: \(String(data: data, encoding: .utf8) ?? "Unable to decode")")
                }
                return (false, nil)
            }
        }
        
        // MARK: - Response Models
        struct PlaceDetailsResponse: Codable {
            let evChargeOptions: EVChargeOptions?
        }
        
        struct EVChargeOptions: Codable {
            let connectorAggregation: [ConnectorAggregation]?
        }
        
        struct ConnectorAggregation: Codable {
            let type: String?
            let maxChargeRateKw: Double?
            let count: Int?
            let availableCount: Int?
            let availabilityLastUpdateTime: String?
            let outOfServiceCount: Int?
        }
        
        func startTimer() {
            timer = Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { _ in
                Task {
                    await refresh()
                }
            }
        }
        
        func stopTimer() {
            timer?.invalidate()
            timer = nil
        }
        
        func formatDate(_ date: Date) -> String {
            let formatter = DateFormatter()
            formatter.dateStyle = .short
            formatter.timeStyle = .medium
            return formatter.string(from: date)
        }
        
        func formatAvailabilityTime(_ isoString: String) -> String {
            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            
            guard let date = formatter.date(from: isoString) else {
                // Try without fractional seconds
                formatter.formatOptions = [.withInternetDateTime]
                guard let date = formatter.date(from: isoString) else {
                    return isoString
                }
                
                let displayFormatter = DateFormatter()
                displayFormatter.dateStyle = .none
                displayFormatter.timeStyle = .short
                return displayFormatter.string(from: date)
            }
            
            let displayFormatter = DateFormatter()
            displayFormatter.dateStyle = .none
            displayFormatter.timeStyle = .short
            return displayFormatter.string(from: date)
        }
}

#Preview {
    ContentView()
}
