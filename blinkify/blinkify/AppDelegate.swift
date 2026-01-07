//
//  AppDelegate.swift
//  blinkify
//
//  Created by Simon Chervenak on 1/7/26.
//

import UIKit

class AppDelegate: NSObject, UIApplicationDelegate {
    private let serverURL = "https://04f85cb0ac48.ngrok-free.app/api/device-token"
        
    func application(_ application: UIApplication,
                    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        UIApplication.shared.registerForRemoteNotifications()
        return true
    }
    
    func application(_ application: UIApplication,
                    didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        let token = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()
        print("Device Token: \(token)")
        
        sendDeviceTokenToServer(token: token)
    }
    
    func application(_ application: UIApplication,
                    didFailToRegisterForRemoteNotificationsWithError error: Error) {
        print("Failed to register for remote notifications: \(error)")
    }
    
    private func sendDeviceTokenToServer(token: String) {
        guard let url = URL(string: serverURL) else {
            print("Invalid URL")
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body: [String: Any] = ["device_token": token]
        
        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
        } catch {
            print("Error serializing JSON: \(error)")
            return
        }
        
        let task = URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                print("Error sending token to server: \(error)")
                return
            }
            
            if let httpResponse = response as? HTTPURLResponse {
                if httpResponse.statusCode == 200 {
                    print("Device token successfully sent to server")
                } else {
                    print("Server returned status code: \(httpResponse.statusCode)")
                }
            }
            
            if let data = data,
               let responseString = String(data: data, encoding: .utf8) {
                print("Server response: \(responseString)")
            }
        }
        
        task.resume()
    }
}
