//None of this has been tested on actual electronics (TEST NEXT TIME ONE OF US IS IN THE LAB!)
#include <Wire.h> //library for how ports are to handle data
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>
#include <Adafruit_BMP3XX.h>
#include <utility/imumaths.h>

#define SEALEVELPRESSURE_HPA (1017.2) //was huntsville hPA when i was making this code

//create sensor instances
Adafruit_BNO055 bno = Adafruit_BNO055(55, 0x28); //the standard I2C address is 0x28 (ours might be 0x29 PLEASE CHECK FIRST)
Adafruit_BMP3XX bmp;

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10); //wait for Serial Monitor to open

  Serial.println(F("Adafruit BNO055 and BMP388 Test ---"));

  //Will probably need to change the pin numbers but this is what i got for now
  Wire.setSDA(6); //assign the GP4 to the SDA
  Wire.setSCL(7); //asign the GP5 to the SCL, then start I2C bus
  Wire.begin();

  //initialize BNO055 for orientation
  if (!bno.begin()) {
    Serial.println(F("ERROR: BNO055 not detected. Check wiring or I2C address now!"));
    while (1);
  }
  
  bno.setExtCrystalUse(true); //I'm not joking when i say this uses a crystal inside the chip (yes i was confused as well)

  //initialize BMP388 for pressure
  if (!bmp.begin_I2C()) { // BMP388 defaults to 0x77 I2C address (might be but should be able to pass 0x76 if needed)
    Serial.println(F("ERROR: BMP388 not detected. Check wiring now!"));
    while (1);
  }

  // Set up the oversampling and filter configuration for the BMP388
  bmp.setTemperatureOversampling(BMP3_OVERSAMPLING_8X); //averages temperature measurements (should make data smoother)
  bmp.setPressureOversampling(BMP3_OVERSAMPLING_4X); //averages pressure measurements so that breezes and the like dont screw up the data
  bmp.setIIRFilterCoeff(BMP3_IIR_FILTER_COEFF_3); //activates the BMP's shock absorber and combines prevoius pressure readings with a new reading
  bmp.setOutputDataRate(BMP3_ODR_50_HZ); //sets sensor refresh rate //DO NOT PUT LOWER THAN 10HZ
 //these are the official adafruit recommendations for handheld devices and drones. So, we should not have to change them

  Serial.println(F("All sensors initialized! Hooray!\n"));
}

void loop() {
  // READ BNO055 DATA 
  sensors_event_t orientationData;
  bno.getEvent(&orientationData, Adafruit_BNO055::VECTOR_EULER);

  // READ BMP388 DATA
  if (!bmp.performReading()) {
    Serial.println(F("Failed to perform reading from BMP388 :("));
    return;
  }

  // PRINT COMBINED DATA TO SERIAL MONITOR 
  Serial.print(F("Heading/Yaw (x): "));
  Serial.print(orientationData.orientation.x, 2);
  Serial.print(F(" | Pitch (y): "));
  Serial.print(orientationData.orientation.y, 2);
  Serial.print(F(" | Roll (z): "));
  Serial.print(orientationData.orientation.z, 2);

  Serial.print(F("  ||  Temp: "));
  Serial.print(bmp.temperature, 2);
  Serial.print(F(" *C | Press: "));
  Serial.print(bmp.pressure / 100.0, 2); // Converts Pascals to hPa
  Serial.print(F(" hPa | Est. Alt: "));
  Serial.print(bmp.readAltitude(SEALEVELPRESSURE_HPA), 2);
  Serial.println(F(" m"));

  delay(100);   // delayed to prevent serial buffer overflow (UNTESTED SO MIGHT NEED CHANGE)
}

