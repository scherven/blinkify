//
//  blinkifyApp.swift
//  blinkify
//
//  Created by Simon Chervenak on 1/5/26.
//

import SwiftUI

@main
struct blinkifyApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}
