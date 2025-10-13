$ErrorActionPreference = "Stop"
$BASE = "http://127.0.0.1:8000"

function Log($msg){ Write-Host "$(Get-Date -Format o)  $msg" }

try {
    Log "Creating room as Alice..."
    $create = Invoke-RestMethod -Method Post -Uri "$BASE/rooms/create_room?player=Alice"
    $room = $create.room_id
    Log "Created room: $room"

    Log "Joining Bob, Carol, Dave..."
    Invoke-RestMethod -Method Post -Uri "$BASE/rooms/join_room?room_id=$room&player=Bob" | Out-Null
    Invoke-RestMethod -Method Post -Uri "$BASE/rooms/join_room?room_id=$room&player=Carol" | Out-Null
    Invoke-RestMethod -Method Post -Uri "$BASE/rooms/join_room?room_id=$room&player=Dave" | Out-Null
    Log "All players joined."

    Log "Starting game..."
    $start = Invoke-RestMethod -Method Post -Uri "$BASE/rooms/start_game?room_id=$room"
    Log ("Game started. Current player: {0}" -f $start.current_player)

    # set hands to produce a chi scenario: Alice will discard 5; Bob (next) has 4 and 6
    Log "Setting hands (admin)..."
    $aliceHand = ,5 + (10..20)[0..11]  # ensure 13 tiles (one is 5)
    $bobHand = 4,6 + (11..30)[0..10]
    $carolHand = (20..32)[0..12]
    $daveHand = (30..42)[0..12]

    Invoke-RestMethod -Method Post -Uri "$BASE/rooms/admin/set_hand?room_id=$room&player=Alice" -Body ($aliceHand | ConvertTo-Json) -ContentType "application/json" | Out-Null
    Invoke-RestMethod -Method Post -Uri "$BASE/rooms/admin/set_hand?room_id=$room&player=Bob" -Body ($bobHand | ConvertTo-Json) -ContentType "application/json" | Out-Null
    Invoke-RestMethod -Method Post -Uri "$BASE/rooms/admin/set_hand?room_id=$room&player=Carol" -Body ($carolHand | ConvertTo-Json) -ContentType "application/json" | Out-Null
    Invoke-RestMethod -Method Post -Uri "$BASE/rooms/admin/set_hand?room_id=$room&player=Dave" -Body ($daveHand | ConvertTo-Json) -ContentType "application/json" | Out-Null
    Log "Hands set."

    Log "Alice discards tile 5..."
    $disc = Invoke-RestMethod -Method Post -Uri "$BASE/rooms/discard_tile?room_id=$room&player=Alice&tile=5"
    Log ("Discard response: {0}" -f ($disc | ConvertTo-Json -Depth 3))

    Start-Sleep -Milliseconds 500

    Log "Bob claims chi with tiles 4,6..."
    $claim = Invoke-RestMethod -Method Post -Uri "$BASE/rooms/claim?room_id=$room&player=Bob&action=chi&tiles=4,6"
    Log ("Claim response: {0}" -f ($claim | ConvertTo-Json -Depth 4))

    Log "Demo flow complete. To observe websocket events, run: python scripts/ws_test.py"
} catch {
    Log "ERROR: $($_.Exception.Message)"
    if ($_.InvocationInfo) { Log ("At: " + $_.InvocationInfo.PositionMessage) }
    exit 1
}