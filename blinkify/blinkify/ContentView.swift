//
//  ContentView.swift
//  blinkify
//
//  Created by Simon Chervenak on 1/5/26.
//

import SwiftUI

struct ContentView: View {
    @State private var isGreen = Bool.random()
    @State private var lastRefreshed = Date()
    @State private var timer: Timer?
    
    private var PLACE_ID = "ChIJlf0s_HFLtokRRa9H_ouBaLM"
    private var API_KEY = Key.key
    
    var body: some View {
        ZStack {
            // Background color
            (isGreen ? Color.green : Color.red)
                .ignoresSafeArea()
            
            VStack {
                // Last refreshed timestamp at top
                Text("Last refreshed: \(formatDate(lastRefreshed))")
                    .foregroundColor(.white)
                    .padding()
                    .font(.headline)
                
                Spacer()
            }
        }
        .refreshable {
            refresh()
        }
        .onAppear {
            startTimer()
        }
        .onDisappear {
            stopTimer()
        }
    }
    
    func refresh() {
        isGreen = Bool.random()
        lastRefreshed = Date()
    }
    
    func startTimer() {
        timer = Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { _ in
            refresh()
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
}

#Preview {
    ContentView()
}
