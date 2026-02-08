//
//  HikeDetailList.swift
//  bus2hike
//
//  Created by Antonia Stieger on 03.02.26.
//

import SwiftUI
import MapKit

struct HikeDetailList: View {
   @Binding var hikes: [Hike]
   @Binding var selectedHike: Hike?
   
   @Binding var showList: Bool
   @Binding var isLoading: Bool
   
   var onSelect: (Hike) -> Void
   var onClose: () -> Void
   
   var body: some View {
      ZStack(alignment: .trailing) {
         if showList {
            Color.black.opacity(0.2)
               .ignoresSafeArea()
               .onTapGesture {
                  withAnimation {
                     showList = false
                     onClose()
                  }
               }
            
            VStack(alignment: .leading, spacing: 16) {
               HStack {
                  Text("Hikes")
                     .font(.title.bold())
                  Spacer()
                  Button {
                     withAnimation {
                        showList = false
                        onClose()
                     }
                  } label: {
                     Image(systemName: "xmark.circle.fill")
                        .font(.title2)
                        .foregroundStyle(.blue)
                  }
               }
               .padding(.bottom, 8)
               
               if isLoading {
                  VStack {
                     Spacer()
                     HStack {
                        Spacer()
                        ProgressView()
                        Spacer()
                     }
                     Spacer()
                  }
               } else {
                  ScrollView {
                     VStack(spacing: 12) {
                        ForEach(hikes) { hike in
                           HikeRow(hike: hike,
                                   isSelected: hike.id == selectedHike?.id) {
                              if hike.id == selectedHike?.id {
                                 selectedHike = nil
                              } else {
                                 selectedHike = hike
                                 onSelect(hike)
                              }
                           }
                        }
                     }
                  }
               }
            }
            .padding()
            .padding(.leading, 12)
            .frame(width: 300)
            .background(.inverted)
            .transition(.move(edge: .trailing))
         }
      }
      .shadow(color: .black.opacity(0.18), radius: 16, x: 0, y: 8)
   }
}

struct HikeRow: View {
   let hike: Hike
   let isSelected: Bool
   let onSelect: () -> Void
   
   var body: some View {
      Button {
         onSelect()
      } label: {
         HStack {
            VStack(alignment: .leading, spacing: 4) {
               Text(hike.name)
                  .font(.headline)
                  .foregroundColor(isSelected ? .white : .primary)
               HStack(spacing: 12) {
                  Text("\(hike.length_km ?? 0.0, specifier: "%.1f") km")
                  Text("\(hike.duration_minutes ?? 0) mins")
                  Text(hike.difficulty ?? "Any")
               }
               .font(.subheadline)
               .foregroundColor(isSelected ? .white.opacity(0.8) : .secondary)
            }
            Spacer()
            if isSelected {
               Image(systemName: "checkmark.circle.fill")
                  .foregroundStyle(.white)
                  .font(.title2)
            }
         }
         .padding(12)
         .background(isSelected ? Color.red : Color.white.opacity(0.05))
         .clipShape(RoundedRectangle(cornerRadius: 12))
      }
      .buttonStyle(.plain)
   }
}

