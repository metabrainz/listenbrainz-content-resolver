# -*- coding: utf-8 -*-
class TagUtils:
  def extract_track_number(track_number):
      if str(track_number).find("/") != -1:
          track_number, dummy = str(track_number).split("/")
      try:
          return_value = int(track_number)
      except ValueError:
          return_value = 0
      return return_value
