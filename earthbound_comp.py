# EarthBound Compressor
# Written by Alchemic
# 2012 Apr 25
# 
# 
# 
# The format is described in greater detail in the decompressor.

from __future__ import division

import sys





# Check if the upcoming bytes are a run of a constant byte.
def lookForConstantByte(buffer, currentIndex):
    # Don't look past the end of the buffer.
    compareLimit = len(buffer) - currentIndex

    # Don't look too far ahead.
    if compareLimit > 1024:
        compareLimit = 1024

    nextByte = buffer[currentIndex]
    matchLength = 0

    for i in xrange(compareLimit):
        if buffer[currentIndex + i] == nextByte:
            matchLength += 1
        else:
            break

    return matchLength, nextByte



# Check if the upcoming words are a run of a constant word.
def lookForConstantWord(buffer, currentIndex):
    # Don't look past the end of the buffer.
    compareLimit = len(buffer) - currentIndex
    if (compareLimit % 2) == 1:
        compareLimit -= 1

    # Don't look too far ahead.
    if compareLimit > 2048:
        compareLimit = 2048

    # We need at least one word remaining to continue.
    if compareLimit < 2:
        return 0, None

    nextWord = buffer[currentIndex+0]
    nextWord += (buffer[currentIndex+1] << 8)
    matchLength = 0

    for i in xrange(0, compareLimit, 2):
        currentWord = buffer[currentIndex + i + 0]
        currentWord += (buffer[currentIndex + i + 1] << 8)
        if currentWord == nextWord:
            matchLength += 2
        else:
            break

    return matchLength, nextWord



# Check if the upcoming bytes are an incrementing run.
def lookForIncrementingByte(buffer, currentIndex):
    # Don't look past the end of the buffer.
    compareLimit = len(buffer) - currentIndex

    # Don't look too far ahead.
    if compareLimit > 1024:
        compareLimit = 1024

    nextByte = buffer[currentIndex]
    matchLength = 0

    for i in xrange(compareLimit):
        if buffer[currentIndex + i] == ((nextByte + i) & 0xFF):
            matchLength += 1
        else:
            break

    return matchLength, nextByte



# Check if the upcoming bytes are a copy of previous bytes.
def lookForPastBytesForward(buffer, currentIndex):
    bestIndex = 0
    bestLength = 0

    # Don't look past the end of the buffer.
    compareLimit = len(buffer) - currentIndex

    # Don't look too far ahead.
    if compareLimit > 1024:
        compareLimit = 1024

    for i in xrange(currentIndex):
        # Count how many sequential bytes match (possibly zero).
        currentLength = 0
        for j in xrange(compareLimit):
            if buffer[i + j] == buffer[currentIndex + j]:
                currentLength += 1
            else:
                break

        # Keep track of the largest match we've seen.
        if currentLength > bestLength:
            bestIndex = i
            bestLength = currentLength

    return bestLength, bestIndex



# Check if the upcoming bytes are a copy of previous bytes.
def lookForPastBytesBitReversed(buffer, bufferBitReversed, currentIndex):
    bestIndex = 0
    bestLength = 0

    # Don't look past the end of the buffer.
    compareLimit = len(bufferBitReversed) - currentIndex

    # Don't look too far ahead.
    if compareLimit > 1024:
        compareLimit = 1024

    for i in xrange(currentIndex):
        # Count how many sequential bytes match (possibly zero).
        currentLength = 0
        for j in xrange(compareLimit):
            if bufferBitReversed[i + j] == buffer[currentIndex + j]:
                currentLength += 1
            else:
                break

        # Keep track of the largest match we've seen.
        if currentLength > bestLength:
            bestIndex = i
            bestLength = currentLength

    return bestLength, bestIndex



# Check if the upcoming bytes are a backward copy of previous bytes.
def lookForPastBytesBackward(buffer, currentIndex):
    bestIndex = 0
    bestLength = 0

    # Don't look past the end of the buffer.
    initialCompareLimit = len(buffer) - currentIndex

    # Don't look too far ahead.
    if initialCompareLimit > 1024:
        initialCompareLimit = 1024

    for i in xrange(currentIndex):
        # Don't look too far back.
        compareLimit = initialCompareLimit
        if compareLimit > i:
            compareLimit = i

        # Count how many sequential bytes match (possibly zero).
        currentLength = 0
        for j in xrange(compareLimit):
            if buffer[i - j] == buffer[currentIndex + j]:
                currentLength += 1
            else:
                break

        # Keep track of the largest match we've seen.
        if currentLength > bestLength:
            bestIndex = i
            bestLength = currentLength

    return bestLength, bestIndex



# Turn a command number, count and argument into compressed data.
def encodeCommand(command, count, argument):
    encodedResult = bytearray()
    count -= 1

    if count < 32:
        encodedResult.append((command << 5) + count)
    else:
        encodedResult.append((7 << 5) + (command << 2) + (count >> 8))
        encodedResult.append(count & 0xFF)

    if command == 0:
        encodedResult.extend(argument)
    elif command == 1:
        encodedResult.append(argument & 0xFF)
    elif command == 2:
        encodedResult.append(argument & 0xFF)
        encodedResult.append((argument & 0xFF00) >> 8)
    elif command == 3:
        encodedResult.append(argument & 0xFF)
    else:
        encodedResult.append((argument & 0xFF00) >> 8)
        encodedResult.append(argument & 0xFF)

    return encodedResult





def compress(inBytes):
    # Prepare for compression.
    buffer = bytearray(inBytes)
    output = bytearray()
    currentIndex = 0

    # Create a copy of the buffer where every the bits of every byte are 
    # reversed (e.g. 0x80 <---> 0x01).
    bufferBitReversed = bytearray(inBytes)
    for currentByte in bufferBitReversed:
        currentByte = ((currentByte >> 4) & 0x0F) | ((currentByte << 4) & 0xF0)
        currentByte = ((currentByte >> 2) & 0x33) | ((currentByte << 2) & 0xCC)
        currentByte = ((currentByte >> 1) & 0x55) | ((currentByte << 1) & 0xAA)

    possibleCommands = {
      1 : lookForConstantByte, 
      2 : lookForConstantWord, 
      3 : lookForIncrementingByte, 
      4 : lookForPastBytesForward, 
      5 : lookForPastBytesBitReversed, 
      6 : lookForPastBytesBackward
    }
    queuedLiterals = bytearray()

    # Main compression loop.
    while currentIndex < len(buffer):
        bestCommand = 0
        bestLength = 2
        bestArgument = 0

        # Find the command that will compress the most upcoming bytes (greedy).
        for commandNumber in possibleCommands:
            if commandNumber == 5:
                # Command 5 copies past bytes, but with the bits of each 
                # byte in reverse order.
                length, argument = possibleCommands[commandNumber](buffer, bufferBitReversed, currentIndex)
            else:
                length, argument = possibleCommands[commandNumber](buffer, currentIndex)

            if length > bestLength:
                bestCommand = commandNumber
                bestLength = length
                bestArgument = argument

        # If none of the commands find a match large enough to be worth 
        # using, the next byte will be encoded as a literal. Don't output 
        # it right away. (If we did, multiple literals in a row would be 
        # encoded as several one-byte commands instead of a single 
        # multi-byte command.)
        if bestCommand == 0:
            queuedLiterals.append(buffer[currentIndex])
            currentIndex += 1
            continue

        # If we've reached this point, we have a non-literal command 
        # to output. If we have any literals queued, output them now.
        if len(queuedLiterals) > 0:
            output += encodeCommand(0, len(queuedLiterals), queuedLiterals)
            queuedLiterals = bytearray()

        # Output the non-literal command.
        if bestCommand == 2:
            # Command 2 (run of a constant word) uses words instead of bytes.
            output += encodeCommand(bestCommand, bestLength // 2, bestArgument)
        else:
            output += encodeCommand(bestCommand, bestLength, bestArgument)

        # Advance the current position in the buffer.
        currentIndex += bestLength

    # Output any leftover queued literals.
    if len(queuedLiterals) > 0:
        output += encodeCommand(0, len(queuedLiterals), queuedLiterals)

    # Append the 0xFF terminator.
    output.append(0xFF)

    # Return the compressed data.
    return output





if __name__ == "__main__":

    # Check for incorrect usage.
    argc = len(sys.argv)
    if argc < 2 or argc > 4:
        sys.stdout.write("Usage: ")
        sys.stdout.write("{0:s} ".format(sys.argv[0]))
        sys.stdout.write("<inFile> [outFile] [outOffset]\n")
        sys.exit(1)

    # Copy the arguments.
    inFile = sys.argv[1]
    outFile = None
    if argc == 3 or argc == 4:
        outFile = sys.argv[2]
    outOffset = 0
    if argc == 4:
        outOffset = int(sys.argv[3], 16)

    # Open, read and close the input file.
    inStream = open(inFile, "rb")
    inBytes = inStream.read()
    inStream.close()

    # Compress the data.
    outBytes = compress(inBytes)

    # Write the compressed output, if appropriate.
    if outFile is not None:
        # Mode r+b gives an error if the file doesn't already exist.
        open(outFile, "a").close()
        outStream = open(outFile, "r+b")
        outStream.seek(outOffset)
        outStream.write(outBytes)
        outStream.close()

    # Report statistics on the data.
    sys.stdout.write("Uncompressed size: 0x{0:X} ({0:d}) bytes\n".format(len(inBytes)))
    sys.stdout.write("Compressed size: 0x{0:X} ({0:d}) bytes\n".format(len(outBytes)))
    sys.stdout.write("Ratio: {0:f}\n".format(len(outBytes) / len(inBytes)))

    # Exit.
    sys.exit(0)
