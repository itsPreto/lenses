import requests
import json

url = "http://127.0.0.1:5000/tree_sit/analyze_pr"
headers = {"Content-Type": "application/json"}

pr_diff = """
diff --git a/org/gtri/deltaxray/dalxisdmain/passengerexperience/content/metadata/sources/network/MetadataApiService.kt b/org/gtri/deltaxray/dalxisdmain/passengerexperience/content/metadata/sources/network/MetadataApiService.kt
index 1234567..abcdefg 100644
--- a/org/gtri/deltaxray/dalxisdmain/passengerexperience/content/metadata/sources/network/MetadataApiService.kt
+++ b/org/gtri/deltaxray/dalxisdmain/passengerexperience/content/metadata/sources/network/MetadataApiService.kt
@@ -68,7 +68,7 @@ class MetadataApiService @Inject constructor(
             .map {
                 if (!it.isError) {
                     val response = it.response()!!
-                    if (response.isSuccessful) {
+                    if (response.isSuccessful && response.code() == 200) {
                         val manifest = it.response()!!.body()!!
                         LogManager.d(TAG, "Got manifest: $manifest")
                         NetworkAvailability.Available(manifest)
@@ -94,6 +94,7 @@ class MetadataApiService @Inject constructor(
             }
             .retryBoundedBackoff("manifest.json", start = retryTimeout)
             .onErrorResumeNext(Maybe.just(NetworkAvailability.Unavailable("Couldn't retrieve manifest from server")))
+            .subscribeOn(scheduler)
     }

     fun getJson(fileName: String): Maybe<NetworkAvailability<JsonArray>> {
@@ -105,6 +106,7 @@ class MetadataApiService @Inject constructor(
                     NetworkAvailability.Available(it)
                 }
             }
+            .subscribeOn(scheduler)
     }

     companion object {
"""

payload = {"pr_diff": pr_diff}

response = requests.post(url, headers=headers, data=json.dumps(payload))

print(f"Status Code: {response.status_code}")
print(f"Response JSON:")
print(json.dumps(response.json(), indent=2))
